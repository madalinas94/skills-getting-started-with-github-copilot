"""Toate apelurile către Claude, într-un singur loc.

Principiu cost-effective: Claude NU face niciodată calcule și nu primește lista
de tranzacții. Primește doar:
  1. lista de comercianți necunoscuți (un singur apel batch / upload) -> categorii
  2. o poză de bon -> {comerciant, dată, total}
  3. întrebarea utilizatorului -> un filtru JSON; suma o calculează Python.
Rezultatele se cachează pe disc, deci același input nu se plătește de două ori.
"""
from __future__ import annotations

import base64
import json
import os
import threading
from pathlib import Path

CATEGORII = [
    "Mâncare", "Transport", "Utilități", "Locuință", "Sănătate",
    "Divertisment", "Shopping", "Călătorii", "Venituri", "Altele",
]

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("CLAUDE_EFFORT", "low")

# $ per 1M tokeni (input, output) – doar pentru afișarea costului estimat în UI
_PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}

_lock = threading.Lock()
usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_hits": 0, "cost_usd": 0.0}


class AIUnavailable(RuntimeError):
    pass


def _load_dotenv() -> None:
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
_client = None


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if not enabled():
        raise AIUnavailable("ANTHROPIC_API_KEY nu este setată.")
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(max_retries=2, timeout=60.0)
    return _client


def _call_json(system: str, content, schema: dict, max_tokens: int = 4000) -> dict:
    """Un apel cu output structurat (JSON garantat valid pe schemă)."""
    import anthropic

    client = _get_client()
    # dacă modelul refuză din greșeală o cerere, serverul reîncearcă pe alt model
    # (disponibil pe Opus / Sonnet / Fable; Haiku nu are fallback pe server)
    extra = {} if "haiku" in MODEL else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            # system prompt stabil + cache: apelurile repetate plătesc ~10% pe prefix
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema}},
            **extra,
        )
    except anthropic.AuthenticationError as e:
        raise AIUnavailable("Cheia API este invalidă.") from e
    except anthropic.APIConnectionError as e:
        raise AIUnavailable("Nu mă pot conecta la API-ul Claude.") from e
    except anthropic.APIStatusError as e:
        raise AIUnavailable(f"Eroare API Claude ({e.status_code}).") from e

    _track(resp)
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise AIUnavailable(f"Răspuns incomplet de la model ({resp.stop_reason}).")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)


def _track(resp) -> None:
    u = resp.usage
    inp = (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
    cached = getattr(u, "cache_read_input_tokens", 0) or 0
    out = u.output_tokens or 0
    pin, pout = _PRICES.get(MODEL, (4.0, 20.0))
    with _lock:
        usage["calls"] += 1
        usage["input_tokens"] += inp + cached
        usage["output_tokens"] += out
        usage["cost_usd"] += (inp * pin + cached * pin * 0.1 + out * pout) / 1_000_000


# ------------------------------------------------------------- 1. categorii

_CAT_SYSTEM = f"""Ești un clasificator de tranzacții bancare din România.
Pentru fiecare descriere primită alegi EXACT o categorie din lista fixă:
{", ".join(CATEGORII)}.
Ghid: supermarket, restaurant, cafenea, livrare mâncare (Glovo, Bolt Food) = Mâncare;
taxi/ride-sharing (Bolt, Uber), carburant, RCA/asigurare auto, parcare = Transport;
curent, gaz, apă, internet, TV, telefon = Utilități; chirie, întreținere = Locuință;
farmacie, clinică = Sănătate; streaming, cinema, jocuri = Divertisment;
magazine online, haine, electronice, articole sport = Shopping;
hotel, zbor, booking = Călătorii; salariu, dobândă, transfer primit = Venituri;
comisioane bancare și orice altceva = Altele.
Câmpul "directie" spune dacă banii au intrat (credit) sau au ieșit (debit)."""

_CAT_SCHEMA = {
    "type": "object",
    "properties": {
        "rezultate": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "categorie": {"type": "string", "enum": CATEGORII},
                },
                "required": ["id", "categorie"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["rezultate"],
    "additionalProperties": False,
}


def categorize_batch(items: list[tuple[str, str]]) -> dict[int, str]:
    """items = [(descriere, directie)] -> {index: categorie}. UN singur apel."""
    payload = [{"id": i, "descriere": d, "directie": dirn} for i, (d, dirn) in enumerate(items)]
    data = _call_json(
        _CAT_SYSTEM,
        "Clasifică tranzacțiile:\n" + json.dumps(payload, ensure_ascii=False),
        _CAT_SCHEMA,
        max_tokens=4000 + 40 * len(items),
    )
    return {r["id"]: r["categorie"] for r in data.get("rezultate", []) if r.get("categorie") in CATEGORII}


# ------------------------------------------------------------- 2. bonuri / documente

_DOC_SYSTEM = f"""Extragi date din bonuri fiscale și documente financiare românești.
Returnezi doar ce scrie efectiv pe document. Sumele sunt numere cu punct zecimal
(ex. 1249.99). Datele în format AAAA-LL-ZZ (pe bonurile românești data e zi/lună/an).
Pentru un bon: o singură tranzacție cu TOTAL-ul de plată (nu fiecare produs).
Categoria se alege din: {", ".join(CATEGORII)}."""

_DOC_SCHEMA = {
    "type": "object",
    "properties": {
        "tranzactii": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "data": {"type": "string"},
                    "descriere": {"type": "string"},
                    "suma": {"type": "number"},
                    "moneda": {"type": "string", "enum": ["RON", "EUR", "USD"]},
                    "directie": {"type": "string", "enum": ["debit", "credit"]},
                    "categorie": {"type": "string", "enum": CATEGORII},
                    "metoda_plata": {"type": "string"},
                },
                "required": ["data", "descriere", "suma", "moneda", "directie", "categorie", "metoda_plata"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["tranzactii"],
    "additionalProperties": False,
}


def extract_document(raw: bytes, media_type: str, kind: str = "bon") -> list[dict]:
    b64 = base64.standard_b64encode(raw).decode()
    if media_type == "application/pdf":
        block = {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": b64}}
        instr = "Extrage toate tranzacțiile din acest extras de cont (fără rândurile de sold)."
    else:
        block = {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}
        instr = "Extrage tranzacția din acest bon fiscal (comerciant, dată, TOTAL, monedă)."
    data = _call_json(_DOC_SYSTEM, [block, {"type": "text", "text": instr}], _DOC_SCHEMA, max_tokens=6000)
    return data.get("tranzactii", [])


# ------------------------------------------------------------- 3. întrebări

QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "operatie": {
            "type": "string",
            "enum": ["suma", "numar", "lista", "medie", "maxim", "pe_categorii", "pe_comercianti"],
        },
        "tip": {"type": "string", "enum": ["cheltuieli", "venituri", "toate"]},
        "categorii": {"type": "array", "items": {"type": "string", "enum": CATEGORII}},
        "luna": {"type": "string", "description": "AAAA-LL sau gol"},
        "data_de_la": {"type": "string", "description": "AAAA-LL-ZZ sau gol"},
        "data_pana_la": {"type": "string", "description": "AAAA-LL-ZZ sau gol"},
        "text_cautat": {"type": "string", "description": "cuvinte din descriere separate prin |, sau gol"},
        "surse": {"type": "array", "items": {"type": "string", "enum": ["card_csv", "extras_pdf", "bon"]}},
        "moneda_originala": {"type": "string", "enum": ["", "RON", "EUR", "USD"]},
        "moneda_afisare": {"type": "string", "enum": ["", "RON", "EUR", "USD"]},
        "limita": {"type": "integer"},
        "interpretare": {"type": "string", "description": "reformularea scurtă a întrebării, în română"},
        "in_afara_domeniului": {"type": "boolean"},
    },
    "required": [
        "operatie", "tip", "categorii", "luna", "data_de_la", "data_pana_la", "text_cautat",
        "surse", "moneda_originala", "moneda_afisare", "limita", "interpretare", "in_afara_domeniului",
    ],
    "additionalProperties": False,
}

_Q_SYSTEM = f"""Transformi întrebări în română SAU engleză despre cheltuieli personale într-un filtru JSON.
NU calculezi nimic: un program aplică filtrul pe tranzacții și face calculele.
Reguli:
- Categorii posibile: {", ".join(CATEGORII)}. „mâncare”, „alimente”, „restaurante” = Mâncare;
  „facturi”, „utilități” = Utilități; „chirie” = Locuință; „ieșiri în oraș” = Mâncare + Divertisment.
- „cheltuit”, „plătit”, „dat pe” => tip „cheltuieli”. „încasat”, „câștigat”, „venit” => „venituri”.
- O lună fără an => folosește anul din lunile disponibile. Fără perioadă => lasă gol (toate datele).
- „Cât” => operatie „suma”; „câte” => „numar”; „care/ce/arată” => „lista”;
  „cea mai mare” => „maxim”; „pe ce categorii”/„distribuție” => „pe_categorii”;
  „la ce magazine”/„top comercianți” => „pe_comercianti”; „în medie” => „medie”.
- „în euro/dolari/lei” la afișare => moneda_afisare. „tranzacțiile făcute în euro” => moneda_originala.
- „cash”, „numerar”, „bonuri” => surse [„bon”]; „pe card” => [„card_csv”]; „din extras” => [„extras_pdf”].
- text_cautat: pentru un subset dintr-o categorie (ex. „livrări și cafenele”, „benzinării”), pune cuvintele-cheie
  din descrierile comercianților separate prin |, ex. "glovo|bolt food|tazz|starbucks|cafe|restaurant" sau "omv|petrom|mol|rompetrol";
  atunci lasă „categorii” gol. Pentru un singur comerciant, doar numele lui (ex. "lidl").
- limita: 0 dacă nu se cere un top anume.
- in_afara_domeniului = true dacă întrebarea nu are legătură cu tranzacțiile.
- Echivalențe în engleză: "how much did I spend" = suma/cheltuieli, "income/earned" = venituri,
  "food/groceries/restaurants" = Mâncare, "bills" = Utilități, "rent" = Locuință, "cash" = surse [„bon”].
- Câmpul „interpretare” îl scrii în limba indicată în mesaj."""


def parse_question(question: str, context: dict) -> dict:
    # Contextul variabil (lunile disponibile) vine după system prompt-ul cachat.
    content = (
        f"Luni disponibile în date: {', '.join(context.get('luni', [])) or 'necunoscut'}.\n"
        f"Limba pentru „interpretare”: {'engleză' if context.get('lang') == 'en' else 'română'}.\n"
        f"Întrebare: {question}"
    )
    return _call_json(_Q_SYSTEM, content, QUERY_SCHEMA, max_tokens=3000)


# ------------------------------------------------------------- 4. sfaturi personalizate

_TIPS_SYSTEM = """Ești Finn, un asistent financiar prietenos pentru utilizatori din România.
Primești DOAR totaluri agregate ale cheltuielilor unei luni (nu tranzacții individuale).
Dai 3-4 sfaturi concrete, personalizate pe cifrele primite, în limba cerută, ton cald și direct.
Fiecare sfat: un titlu scurt (max 6 cuvinte), o explicație de 1-2 propoziții care citează
cifrele reale, și o estimare realistă a economiei lunare în moneda primită (0 dacă nu se aplică).
Nu inventa cheltuieli care nu apar în date. Nu recomanda produse financiare anume."""

_TIPS_SCHEMA = {
    "type": "object",
    "properties": {
        "salut": {"type": "string", "description": "o propoziție scurtă, caldă, care rezumă luna"},
        "sfaturi": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titlu": {"type": "string"},
                    "detaliu": {"type": "string"},
                    "economie_lunara": {"type": "number"},
                    "emoji": {"type": "string"},
                },
                "required": ["titlu", "detaliu", "economie_lunara", "emoji"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["salut", "sfaturi"],
    "additionalProperties": False,
}


def personal_tips(summary: dict, lang: str = "ro") -> dict:
    limba = "Răspunde în engleză." if lang == "en" else "Răspunde în română."
    return _call_json(_TIPS_SYSTEM, f"{limba}\n{json.dumps(summary, ensure_ascii=False)}", _TIPS_SCHEMA, max_tokens=4000)
