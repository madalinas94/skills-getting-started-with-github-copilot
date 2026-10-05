"""
Modulul AI pentru propuneri.

Retușează o propunere de proiect (titlu, ce face aplicația, cine o folosește)
și cere detalii DOAR unde lipsesc. Folosește Claude dacă există credențiale
(ANTHROPIC_API_KEY); altfel cade pe un mod local, simplu, bazat pe reguli,
ca aplicația să funcționeze și fără cheie.
"""

import json
import os
import re

MODEL = os.environ.get("CUTIA_MODEL", "claude-opus-5-5")

FIELDS = {
    "title": "titlu",
    "description": "ce face aplicația",
    "audience": "cine o folosește",
}

# Pragul sub care considerăm un câmp "lipsă" în modul local
MIN_LEN = {"title": 3, "description": 25, "audience": 4}

SYSTEM_PROMPT = """Ești asistentul din „Cutia Clasei", o aplicație în care studenții \
propun proiecte pentru ora următoare. Primești o propunere cu trei câmpuri: \
titlu, ce face aplicația (description) și cine o folosește (audience).

Sarcina ta:
1. Retușează fiecare câmp: corectează gramatica și diacriticele, fă textul clar \
și concis, păstrează ideea și vocea studentului. Nu inventa funcții sau detalii noi.
2. Pentru fiecare câmp care lipsește sau e prea vag ca să înțelegi propunerea, \
adaugă în "missing" o întrebare scurtă și concretă. Dacă un câmp e suficient de \
clar, NU pune întrebări despre el. Dacă totul e clar, "missing" e o listă goală.
3. Dacă un câmp lipsește complet, lasă-l gol în varianta retușată.
4. În "notes" scrie o singură propoziție despre ce ai schimbat.

Răspunde în limba română."""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "audience": {"type": "string"},
        "missing": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(FIELDS)},
                    "question": {"type": "string"},
                },
                "required": ["field", "question"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["title", "description", "audience", "missing", "notes"],
    "additionalProperties": False,
}


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text


def _sentence(text: str) -> str:
    text = _clean(text)
    if text and text[-1] not in ".!?":
        text += "."
    return text


LOCAL_QUESTIONS = {
    "title": "Cum s-ar numi aplicația? Alege un nume scurt.",
    "description": "Descrie pe scurt 2-3 lucruri pe care le poate face un utilizator.",
    "audience": "Pentru cine e aplicația? (de ex. studenții, trainerul, părinții)",
}


def refine_local(title: str, description: str, audience: str) -> dict:
    """Retușare simplă fără AI: curăță spațiile, majuscule, punctuație."""
    raw = {"title": title, "description": description, "audience": audience}
    refined = {
        "title": _clean(title).rstrip("."),
        "description": _sentence(description),
        "audience": _clean(audience).rstrip("."),
    }
    missing = [
        {"field": f, "question": LOCAL_QUESTIONS[f]}
        for f in FIELDS
        if len((raw[f] or "").strip()) < MIN_LEN[f]
    ]
    for item in missing:
        if not (raw[item["field"]] or "").strip():
            refined[item["field"]] = ""
    return {
        **refined,
        "missing": missing,
        "notes": "Retușare locală (fără AI): am curățat spațiile, majusculele și punctuația.",
        "engine": "local",
    }


def _client():
    try:
        import anthropic
    except ImportError:
        return None
    try:
        return anthropic.Anthropic()
    except Exception:
        return None


def refine(title: str, description: str, audience: str) -> dict:
    """Retușează propunerea cu Claude; dacă nu se poate, folosește modul local."""
    mode = os.environ.get("CUTIA_AI", "auto")
    has_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if mode == "off" or (mode == "auto" and not has_key):
        return refine_local(title, description, audience)
    client = _client()
    if client is None:
        return refine_local(title, description, audience)

    import anthropic

    payload = json.dumps(
        {"title": title, "description": description, "audience": audience},
        ensure_ascii=False,
    )
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            messages=[{"role": "user", "content": f"Propunerea:\n{payload}"}],
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            return refine_local(title, description, audience)
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
    except (anthropic.APIError, StopIteration, json.JSONDecodeError, TypeError):
        return refine_local(title, description, audience)

    data["missing"] = [m for m in data.get("missing", []) if m.get("field") in FIELDS]
    data["engine"] = "claude"
    return data
