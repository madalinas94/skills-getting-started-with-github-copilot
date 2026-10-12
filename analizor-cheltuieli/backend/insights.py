"""Recomandări, atenționări, scor financiar și tabele de analiză.

Totul se calculează local, cu reguli transparente: e gratuit, instant și
aceleași date dau mereu aceleași sfaturi. AI-ul e folosit opțional doar
pentru „sfaturi personalizate”, iar atunci primește doar totaluri agregate.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from .store import convert, fmt, merchant_name, month_label

# Buget orientativ, ca procent din venitul lunar (inspirat din regula 50/30/20).
BUDGET_SHARE = {
    "Locuință": 30, "Mâncare": 15, "Transport": 10, "Utilități": 7, "Sănătate": 5,
    "Divertisment": 5, "Shopping": 7, "Călătorii": 5, "Altele": 3,
}
NEEDS = {"Locuință", "Utilități", "Sănătate", "Transport"}

EATING_OUT = r"glovo|bolt food|tazz|restaurant|bistro|pizza|starbucks|cafe|coffee|mcdonald|kfc|bar "
SUBSCRIPTIONS = r"netflix|spotify|hbo|disney|youtube|apple\.com|google|digi|orange|vodafone|telekom|max\b|prime"
STREAMING = r"netflix|spotify|hbo|disney|youtube|prime|max\b"
FUEL = r"omv|petrom|mol\b|rompetrol|lukoil|socar|gazprom"
RIDES = r"bolt(?!\s*food)|uber|taxi|free now"
FEES = r"comision|taxa administrare|cost administrare"
GROCERIES = r"mega image|lidl|kaufland|carrefour|auchan|profi|penny|alimentar|supermarket"


def _ron(t: dict) -> float:
    return convert(t["amount"], t["currency"], "RON")


def _match(t: dict, pattern: str) -> bool:
    return re.search(pattern, t["description"].lower()) is not None


def build(txs: list[dict], month: str, cur: str) -> dict:
    """txs = tranzacții active (fără duplicate). month = 'AAAA-LL' sau '' pentru toate."""
    rows = [t for t in txs if not month or t["date"].startswith(month)]
    exp = [t for t in rows if t["direction"] == "debit" and t["category"] != "Venituri"]
    inc = [t for t in rows if t["direction"] == "credit"]
    E = sum(_ron(t) for t in exp)
    I = sum(_ron(t) for t in inc)
    c = lambda v: round(convert(v, "RON", cur), 2)  # noqa: E731
    f = lambda v: fmt(convert(v, "RON", cur), cur)  # noqa: E731
    period = month_label(month) if month else "toată perioada"

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for t in exp:
        by_cat[t["category"]].append(t)

    eating = [t for t in exp if t["category"] == "Mâncare" and _match(t, EATING_OUT)]
    eating_sum = sum(_ron(t) for t in eating)
    wants_cats = {"Divertisment", "Shopping", "Călătorii", "Altele"}
    needs = sum(_ron(t) for t in exp if t["category"] in NEEDS) + sum(_ron(t) for t in by_cat["Mâncare"]) - eating_sum
    wants = sum(_ron(t) for t in exp if t["category"] in wants_cats) + eating_sum
    savings = I - E

    alerts: list[dict] = []
    recs: list[dict] = []

    # ------------------------------------------------------------ atenționări
    if I > 0 and savings < 0:
        alerts.append(_alert("danger", "Ai cheltuit mai mult decât ai încasat",
                             f"În {period} cheltuielile ({f(E)}) depășesc încasările ({f(I)}) cu {f(-savings)}."))
    elif I > 0 and savings / I < 0.1:
        alerts.append(_alert("warn", "Rată de economisire mică",
                             f"Pui deoparte doar {savings / I:.0%} din venit. Ținta sănătoasă e de cel puțin 20%."))
    elif I > 0:
        alerts.append(_alert("success", "Bravo, economisești!",
                             f"Ai rămas cu {f(savings)}, adică {savings / I:.0%} din venit."))

    # chiria și facturile sunt fixe și așteptate, deci nu le tratăm ca „vârfuri”
    variable = [t for t in exp if t["category"] not in ("Locuință", "Utilități")]
    if variable:
        big = max(variable, key=_ron)
        if E and _ron(big) / E >= 0.15:
            alerts.append(_alert("warn", "Cheltuială mare, ocazională",
                                 f"{merchant_name(big['description'])}, pe {_d(big['date'])}: {f(_ron(big))} "
                                 f"({_ron(big) / E:.0%} din cheltuielile lunii)."))
        days: dict[str, float] = defaultdict(float)
        for t in variable:
            days[t["date"]] += _ron(t)
        avg_day = sum(days.values()) / max(len(days), 1)
        peak_day, peak = max(days.items(), key=lambda kv: kv[1])
        if peak > 3 * avg_day and len(days) > 4 and peak_day != big["date"]:
            alerts.append(_alert("info", "Zi cu vârf de cheltuieli",
                                 f"Pe {_d(peak_day)} ai cheltuit {f(peak)}, de {peak / avg_day:.0f}× peste media zilnică."))

    rent = sum(_ron(t) for t in by_cat["Locuință"])
    if I and rent / I > 0.30:
        alerts.append(_alert("warn", "Chiria cântărește mult",
                             f"Locuința înseamnă {rent / I:.0%} din venit. Recomandat e sub 30%."))

    foreign = [t for t in exp if t["currency"] != "RON"]
    if foreign:
        alerts.append(_alert("info", "Plăți în valută",
                             f"{len(foreign)} {'plată' if len(foreign) == 1 else 'plăți'} în {', '.join(sorted({t['currency'] for t in foreign}))}, "
                             f"în total {f(sum(_ron(t) for t in foreign))}. Banca poate percepe comision de conversie."))
    other = by_cat.get("Altele", [])
    if len(other) >= 3:
        alerts.append(_alert("info", "Tranzacții necategorisite",
                             f"{len(other)} tranzacții sunt la „Altele”. Le poți recategorisi din tabel."))

    # ------------------------------------------------------------ recomandări
    if eating_sum > 0:
        recs.append(_rec(
            "food", "🍽️", "Livrări și ieșiri în oraș", "high" if eating_sum > 300 else "medium",
            f"Ai dat {f(eating_sum)} pe {len(eating)} comenzi, cafele și restaurante "
            f"(media {f(eating_sum / len(eating))} pe comandă).",
            eating_sum * 0.4,
            ["Gătește în avans duminica pentru 3–4 zile: o porție gătită acasă costă cam o treime dintr-o livrare.",
             "Limitează livrările la o seară pe săptămână și comandă cu prietenii, ca să împărțiți taxa de livrare.",
             "Ia cafea la termos. 2 cafele pe săptămână la cafenea înseamnă peste 1.000 RON pe an."],
        ))

    subs = [t for t in exp if _match(t, SUBSCRIPTIONS)]
    if subs:
        stream = [t for t in subs if _match(t, STREAMING)]
        recs.append(_rec(
            "subs", "📺", "Abonamente recurente", "medium",
            f"{len(subs)} abonamente costă {f(sum(_ron(t) for t in subs))} pe lună, adică "
            f"{f(sum(_ron(t) for t in subs) * 12)} pe an.",
            sum(_ron(t) for t in stream) * 0.5 if stream else sum(_ron(t) for t in subs) * 0.1,
            ["Folosește planuri Family/Duo împărțite cu alte persoane (economie de 40–60%).",
             "Abonează-te prin rotație: o lună Netflix, o lună alt serviciu, nu toate odată.",
             "Sună furnizorul de internet/TV și cere oferta de fidelizare. Funcționează des."],
        ))

    fuel = [t for t in exp if _match(t, FUEL)]
    rides = [t for t in exp if _match(t, RIDES)]
    if fuel or rides:
        fs, rs = sum(_ron(t) for t in fuel), sum(_ron(t) for t in rides)
        recs.append(_rec(
            "transport", "🚗", "Transport și carburant", "medium" if fs + rs > 300 else "low",
            f"Carburant: {f(fs)} ({len(fuel)} alimentări). Curse ride-sharing: {f(rs)} ({len(rides)} curse).",
            fs * 0.10 + rs * 0.3,
            ["Compară prețul la pompă în aplicații (ex. Peco Online). Diferența ajunge la 0,30 RON/litru.",
             "Folosește cardul de fidelitate al benzinăriei și verifică presiunea în anvelope (consum cu până la 3% mai mic).",
             "Pentru drumuri scurte în oraș, abonamentul de transport public e de obicei mai ieftin decât 2 curse Bolt/Uber."],
        ))

    ins = [t for t in exp if re.search(r"\brca\b|asigur", t["description"].lower())]
    if ins:
        s = sum(_ron(t) for t in ins)
        recs.append(_rec(
            "rca", "🛡️", "Asigurarea auto (RCA)", "low",
            f"Ai plătit {f(s)} pe asigurare. Prețurile diferă mult de la un asigurător la altul.",
            s * 0.15 / 12,
            ["Cere oferte pe un comparator de RCA cu 2–3 săptămâni înainte de expirare.",
             "Un RCA pe 12 luni e de obicei mai ieftin decât două pe câte 6 luni.",
             "Verifică dacă ai clasă bonus-malus bună. Fără daune, prima scade."],
        ))

    fees = [t for t in exp if _match(t, FEES)]
    if fees:
        s = sum(_ron(t) for t in fees)
        recs.append(_rec(
            "fees", "🏦", "Comisioane bancare", "low",
            f"Plătești {f(s)} comisioane, adică {f(s * 12)} pe an, pe care le-ai putea evita.",
            s,
            ["Cere băncii pachetul fără comision de administrare (multe îl oferă pentru încasare salariu).",
             "Sau mută-ți cheltuielile zilnice pe un cont digital gratuit."],
        ))

    shopping = by_cat.get("Shopping", [])
    if shopping:
        s = sum(_ron(t) for t in shopping)
        big = max(shopping, key=_ron)
        recs.append(_rec(
            "shopping", "🛍️", "Cumpărături impulsive", "high" if s > 0.15 * max(E, 1) else "medium",
            f"Shopping: {f(s)}, din care cea mai mare plată a fost {merchant_name(big['description'])} ({f(_ron(big))}).",
            s * 0.2,
            ["Aplică regula celor 48 de ore: pune produsul în coș și decide abia după 2 zile.",
             "Pentru electronice, urmărește istoricul de preț. Reducerile reale apar de Black Friday sau la lansarea modelului nou.",
             "Setează un buget lunar de shopping și ține-l pe un card separat."],
        ))

    groc = [t for t in exp if _match(t, GROCERIES)]
    if groc:
        s = sum(_ron(t) for t in groc)
        recs.append(_rec(
            "groceries", "🛒", "Cumpărături de alimente", "low",
            f"{len(groc)} drumuri la supermarket, total {f(s)} (media {f(s / len(groc))} pe drum).",
            s * 0.1,
            ["Fă lista înainte și mergi o dată pe săptămână: fiecare drum în plus aduce produse neplanificate.",
             "Alege mărcile proprii ale magazinului (cu 20–30% mai ieftine) și urmărește catalogul săptămânal.",
             "Nu face cumpărături când ți-e foame. Sună a clișeu, dar funcționează."],
        ))

    util = by_cat.get("Utilități", [])
    if util:
        s = sum(_ron(t) for t in util)
        recs.append(_rec(
            "util", "💡", "Utilități", "low",
            f"Facturile de utilități: {f(s)} în {period}.",
            s * 0.08,
            ["Becuri LED și prize cu întrerupător pentru aparatele în standby (5–10% din factură).",
             "Compară anual furnizorul de energie pe comparatorul ANRE.",
             "Spală la 30°C și pornește mașina de vase doar plină."],
        ))

    if foreign:
        s = sum(_ron(t) for t in foreign)
        recs.append(_rec(
            "fx", "💱", "Plăți în valută", "low",
            f"Ai plătit {f(s)} în altă monedă decât RON.",
            s * 0.02,
            ["La POS sau online alege plata în moneda locală a comerciantului, nu în RON (evită conversia dinamică DCC).",
             "Folosește un card fără comision de conversie pentru călătorii."],
        ))

    if I > 0 and savings / I < 0.2:
        recs.append(_rec(
            "save", "🐷", "Plătește-te pe tine primul", "high",
            "Nu ai încă un obicei automat de economisire.",
            I * 0.1 if savings > 0 else 0,
            ["Setează un transfer automat de 10% din salariu într-un cont de economii, chiar în ziua salariului.",
             "Construiește un fond de urgență de 3–6 luni de cheltuieli înainte de investiții.",
             "Rotunjește plățile cu cardul și trimite diferența automat în economii (funcție oferită de multe bănci)."],
        ))

    prio = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: (prio[r["priority"]], -r["saving_ron"]))
    potential = sum(r["saving_ron"] for r in recs)
    for r in recs:
        r["saving"] = c(r.pop("saving_ron"))
        r["saving_year"] = round(r["saving"] * 12, 2)

    # ------------------------------------------------------------ scor 0–100
    score = 100
    if I > 0:
        rate = savings / I
        score -= 35 if rate < 0 else 18 if rate < 0.1 else 8 if rate < 0.2 else 0
        score -= 12 if wants / I > 0.4 else 6 if wants / I > 0.3 else 0
        score -= 6 if rent / I > 0.35 else 0
    else:
        score -= 10
    score -= 4 if fees else 0
    score -= 5 if len(subs) >= 4 else 0
    score -= 6 if any(a["level"] == "warn" and "ocazională" in a["title"] for a in alerts) else 0
    score = max(5, min(100, score))
    label = "Excelent" if score >= 80 else "Bun" if score >= 60 else "Atenție" if score >= 40 else "Critic"

    # ------------------------------------------------------------ tabel calitativ categorii
    cat_table = []
    for cat_name, items in sorted(((k, v) for k, v in by_cat.items() if v), key=lambda kv: -sum(_ron(t) for t in kv[1])):
        s = sum(_ron(t) for t in items)
        budget = I * BUDGET_SHARE.get(cat_name, 5) / 100 if I else 0
        ratio = s / budget if budget else 0
        status = ("ok" if ratio <= 1 else "warn" if ratio <= 1.25 else "over") if budget else "na"
        cat_table.append({
            "category": cat_name, "total": c(s), "share": round(s / E * 100, 1) if E else 0,
            "count": len(items), "avg": c(s / len(items)), "max": c(max(_ron(t) for t in items)),
            "budget": c(budget), "budget_pct": BUDGET_SHARE.get(cat_name, 5), "usage": round(ratio * 100),
            "status": status,
        })

    # ------------------------------------------------------------ comercianți
    merch: dict[str, list[dict]] = defaultdict(list)
    for t in exp:
        merch[merchant_name(t["description"])].append(t)
    merchants = sorted(({
        "name": n, "category": items[0]["category"], "visits": len(items),
        "total": c(sum(_ron(t) for t in items)), "avg": c(sum(_ron(t) for t in items) / len(items)),
        "last": max(t["date"] for t in items),
    } for n, items in merch.items()), key=lambda m: -m["total"])

    subs_table = [{
        "name": merchant_name(t["description"]), "monthly": c(_ron(t)), "yearly": c(_ron(t) * 12),
        "category": t["category"],
        "tip": "Verifică dacă îl folosești săptămânal" if _match(t, STREAMING) else "Cere oferta de fidelizare",
    } for t in subs]

    return {
        "period": period, "currency": cur,
        "totals": {"expenses": c(E), "income": c(I), "net": c(savings),
                   "savings_rate": round(savings / I * 100, 1) if I else None,
                   "count": len(exp), "avg_tx": c(E / len(exp)) if exp else 0},
        "score": score, "score_label": label,
        "rule_50_30_20": {"needs": c(needs), "wants": c(wants), "savings": c(max(savings, 0)),
                          "income": c(I),
                          "needs_pct": round(needs / I * 100) if I else 0,
                          "wants_pct": round(wants / I * 100) if I else 0,
                          "savings_pct": round(max(savings, 0) / I * 100) if I else 0},
        "alerts": alerts, "recommendations": recs, "potential_saving": c(potential),
        "potential_saving_year": c(potential * 12),
        "categories": cat_table, "merchants": merchants[:12], "subscriptions": subs_table,
        "headline": _headline(period, E, I, potential, recs, f),
    }


def _headline(period: str, E: float, I: float, potential: float, recs: list[dict], f) -> str:
    if not E and not I:
        return "Încarcă un fișier și îți spun imediat unde îți zboară banii."
    parts = [f"În {period} ai cheltuit {f(E)}"]
    if I:
        parts.append(f"și ai încasat {f(I)}")
    s = " ".join(parts) + "."
    if recs:
        s += f" Am găsit {len(recs)} idei prin care poți economisi aproximativ {f(potential)} pe lună."
    return s


def _alert(level: str, title: str, text: str) -> dict:
    return {"level": level, "title": title, "text": text}


def _rec(rid, icon, title, priority, text, saving_ron, tips) -> dict:
    return {"id": rid, "icon": icon, "title": title, "priority": priority, "text": text,
            "saving_ron": round(max(saving_ron, 0), 2), "tips": tips}


def _d(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def summary_for_ai(ins: dict) -> dict:
    """Doar totaluri agregate, fără nicio tranzacție individuală."""
    return {
        "perioada": ins["period"], "moneda": ins["currency"], "totaluri": ins["totals"],
        "scor": ins["score"], "regula_50_30_20": ins["rule_50_30_20"],
        "categorii": [{k: r[k] for k in ("category", "total", "share", "count", "usage")} for r in ins["categories"]],
        "top_comercianti": [{k: m[k] for k in ("name", "visits", "total")} for m in ins["merchants"][:8]],
        "abonamente": [s["name"] for s in ins["subscriptions"]],
    }
