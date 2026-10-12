"""Recomandări, atenționări, scor financiar, personalitate și tabele de analiză.

Totul se calculează local, cu reguli transparente: e gratuit, instant și
aceleași date dau mereu aceleași sfaturi. AI-ul e folosit opțional doar
pentru „sfaturi personalizate”, iar atunci primește doar totaluri agregate.
Textele sunt generate în română sau engleză (parametrul `lang`).
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from . import i18n
from .store import convert, merchant_name

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


def build(txs: list[dict], month: str, cur: str, lang: str = "ro", budgets: dict[str, float] | None = None) -> dict:
    """txs = tranzacții active (fără duplicate). month = 'AAAA-LL' sau '' pentru toate."""
    lang = i18n.norm(lang)
    L = lambda ro, en: i18n.pick(lang, ro, en)  # noqa: E731
    c = lambda v: round(convert(v, "RON", cur), 2)  # noqa: E731
    f = lambda v: i18n.fmt(convert(v, "RON", cur), cur, lang)  # noqa: E731
    d = lambda iso: i18n.date_label(iso, lang)  # noqa: E731

    rows = [t for t in txs if not month or t["date"].startswith(month)]
    exp = [t for t in rows if t["direction"] == "debit" and t["category"] != "Venituri"]
    inc = [t for t in rows if t["direction"] == "credit"]
    E = sum(_ron(t) for t in exp)
    I = sum(_ron(t) for t in inc)
    period = i18n.month_label(month, lang) if month else L("toată perioada", "the whole period")

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for t in exp:
        by_cat[t["category"]].append(t)

    eating = [t for t in exp if t["category"] == "Mâncare" and _match(t, EATING_OUT)]
    eating_sum = sum(_ron(t) for t in eating)
    wants_cats = {"Divertisment", "Shopping", "Călătorii", "Altele"}
    food_total = sum(_ron(t) for t in by_cat.get("Mâncare", []))
    needs = sum(_ron(t) for t in exp if t["category"] in NEEDS) + food_total - eating_sum
    wants = sum(_ron(t) for t in exp if t["category"] in wants_cats) + eating_sum
    savings = I - E
    rent = sum(_ron(t) for t in by_cat.get("Locuință", []))

    alerts: list[dict] = []
    recs: list[dict] = []

    # ------------------------------------------------------------ atenționări
    if I > 0 and savings < 0:
        alerts.append(_alert("danger", L("Ai cheltuit mai mult decât ai încasat", "You spent more than you earned"),
                             L(f"În {period} cheltuielile ({f(E)}) depășesc încasările ({f(I)}) cu {f(-savings)}.",
                               f"In {period} your spending ({f(E)}) exceeds your income ({f(I)}) by {f(-savings)}.")))
    elif I > 0 and savings / I < 0.1:
        alerts.append(_alert("warn", L("Rată de economisire mică", "Low savings rate"),
                             L(f"Pui deoparte doar {savings / I:.0%} din venit. Ținta sănătoasă e de cel puțin 20%.",
                               f"You only keep {savings / I:.0%} of your income. A healthy target is at least 20%.")))
    elif I > 0:
        alerts.append(_alert("success", L("Bravo, economisești!", "Nice, you're saving!"),
                             L(f"Ai rămas cu {f(savings)}, adică {savings / I:.0%} din venit.",
                               f"You kept {f(savings)}, that's {savings / I:.0%} of your income.")))

    # chiria și facturile sunt fixe și așteptate, deci nu le tratăm ca „vârfuri”
    variable = [t for t in exp if t["category"] not in ("Locuință", "Utilități")]
    big = max(variable, key=_ron) if variable else None
    if big and E and _ron(big) / E >= 0.15:
        alerts.append(_alert("warn", L("Cheltuială mare, ocazională", "Big one-off purchase"),
                             L(f"{merchant_name(big['description'])}, pe {d(big['date'])}: {f(_ron(big))} "
                               f"({_ron(big) / E:.0%} din cheltuielile lunii).",
                               f"{merchant_name(big['description'])} on {d(big['date'])}: {f(_ron(big))} "
                               f"({_ron(big) / E:.0%} of the month's spending).")))
    if variable:
        days: dict[str, float] = defaultdict(float)
        for t in variable:
            days[t["date"]] += _ron(t)
        avg_day = sum(days.values()) / max(len(days), 1)
        peak_day, peak = max(days.items(), key=lambda kv: kv[1])
        if peak > 3 * avg_day and len(days) > 4 and peak_day != big["date"]:
            alerts.append(_alert("info", L("Zi cu vârf de cheltuieli", "Spending spike"),
                                 L(f"Pe {d(peak_day)} ai cheltuit {f(peak)}, de {peak / avg_day:.0f}× peste media zilnică.",
                                   f"On {d(peak_day)} you spent {f(peak)}, {peak / avg_day:.0f}× your daily average.")))
    if I and rent / I > 0.30:
        alerts.append(_alert("warn", L("Chiria cântărește mult", "Rent is heavy"),
                             L(f"Locuința înseamnă {rent / I:.0%} din venit. Recomandat e sub 30%.",
                               f"Housing takes {rent / I:.0%} of your income. The guideline is under 30%.")))
    foreign = [t for t in exp if t["currency"] != "RON"]
    if foreign:
        curs = ", ".join(sorted({t["currency"] for t in foreign}))
        n = len(foreign)
        alerts.append(_alert("info", L("Plăți în valută", "Foreign-currency payments"),
                             L(f"{n} {'plată' if n == 1 else 'plăți'} în {curs}, în total {f(sum(_ron(t) for t in foreign))}. "
                               "Banca poate percepe comision de conversie.",
                               f"{n} payment{'s' if n > 1 else ''} in {curs}, {f(sum(_ron(t) for t in foreign))} in total. "
                               "Your bank may charge a conversion fee.")))
    other = by_cat.get("Altele", [])
    if len(other) >= 3:
        alerts.append(_alert("info", L("Tranzacții necategorisite", "Uncategorised transactions"),
                             L(f"{len(other)} tranzacții sunt la „Altele”. Le poți recategorisi din tabel.",
                               f"{len(other)} transactions are under “Other”. You can recategorise them in the table.")))

    # ------------------------------------------------------------ recomandări
    if eating:
        recs.append(_rec(
            "food", "🍽️", L("Livrări și ieșiri în oraș", "Delivery & eating out"), "high" if eating_sum > 300 else "medium",
            L(f"Ai dat {f(eating_sum)} pe {len(eating)} comenzi, cafele și restaurante (media {f(eating_sum / len(eating))} pe comandă).",
              f"You spent {f(eating_sum)} on {len(eating)} deliveries, coffees and restaurants ({f(eating_sum / len(eating))} each on average)."),
            eating_sum * 0.4,
            L(["Gătește în avans duminica pentru 3–4 zile: o porție gătită acasă costă cam o treime dintr-o livrare.",
               "Limitează livrările la o seară pe săptămână și comandă cu prietenii, ca să împărțiți taxa de livrare.",
               "Ia cafea la termos. 2 cafele pe săptămână la cafenea înseamnă peste 1.000 RON pe an."],
              ["Meal-prep on Sunday for 3–4 days: a home-cooked portion costs about a third of a delivery.",
               "Keep delivery to one night a week and order with friends to split the delivery fee.",
               "Bring coffee in a thermos. Two café coffees a week add up to over 1,000 RON a year."]),
        ))

    subs = [t for t in exp if _match(t, SUBSCRIPTIONS)]
    if subs:
        ss = sum(_ron(t) for t in subs)
        stream = [t for t in subs if _match(t, STREAMING)]
        recs.append(_rec(
            "subs", "📺", L("Abonamente recurente", "Recurring subscriptions"), "medium",
            L(f"{len(subs)} abonamente costă {f(ss)} pe lună, adică {f(ss * 12)} pe an.",
              f"{len(subs)} subscriptions cost {f(ss)} a month, that's {f(ss * 12)} a year."),
            sum(_ron(t) for t in stream) * 0.5 if stream else ss * 0.1,
            L(["Folosește planuri Family/Duo împărțite cu alte persoane (economie de 40–60%).",
               "Abonează-te prin rotație: o lună Netflix, o lună alt serviciu, nu toate odată.",
               "Sună furnizorul de internet/TV și cere oferta de fidelizare. Funcționează des."],
              ["Share Family/Duo plans with others (40–60% cheaper).",
               "Rotate streaming services: one month Netflix, the next another, never all at once.",
               "Call your internet/TV provider and ask for the loyalty offer. It often works."]),
        ))

    fuel = [t for t in exp if _match(t, FUEL)]
    rides = [t for t in exp if _match(t, RIDES)]
    if fuel or rides:
        fs, rs = sum(_ron(t) for t in fuel), sum(_ron(t) for t in rides)
        recs.append(_rec(
            "transport", "🚗", L("Transport și carburant", "Transport & fuel"), "medium" if fs + rs > 300 else "low",
            L(f"Carburant: {f(fs)} ({len(fuel)} alimentări). Curse ride-sharing: {f(rs)} ({len(rides)} curse).",
              f"Fuel: {f(fs)} ({len(fuel)} fill-ups). Ride-hailing: {f(rs)} ({len(rides)} rides)."),
            fs * 0.10 + rs * 0.3,
            L(["Compară prețul la pompă în aplicații (ex. Peco Online). Diferența ajunge la 0,30 RON/litru.",
               "Folosește cardul de fidelitate al benzinăriei și verifică presiunea în anvelope (consum cu până la 3% mai mic).",
               "Pentru drumuri scurte în oraș, abonamentul de transport public e de obicei mai ieftin decât 2 curse Bolt/Uber."],
              ["Compare pump prices in an app (e.g. Peco Online). The difference can reach 0.30 RON/litre.",
               "Use the fuel station loyalty card and keep tyres inflated (up to 3% less fuel).",
               "For short city trips, a public transport pass usually costs less than two Bolt/Uber rides."]),
        ))

    ins = [t for t in exp if re.search(r"\brca\b|asigur", t["description"].lower())]
    if ins:
        s = sum(_ron(t) for t in ins)
        recs.append(_rec(
            "rca", "🛡️", L("Asigurarea auto (RCA)", "Car insurance"), "low",
            L(f"Ai plătit {f(s)} pe asigurare. Prețurile diferă mult de la un asigurător la altul.",
              f"You paid {f(s)} for insurance. Prices vary a lot between insurers."),
            s * 0.15 / 12,
            L(["Cere oferte pe un comparator de RCA cu 2–3 săptămâni înainte de expirare.",
               "Un RCA pe 12 luni e de obicei mai ieftin decât două pe câte 6 luni.",
               "Verifică dacă ai clasă bonus-malus bună. Fără daune, prima scade."],
              ["Get quotes on a comparison site 2–3 weeks before renewal.",
               "A 12-month policy is usually cheaper than two 6-month ones.",
               "Check your no-claims bonus class. No claims means a lower premium."]),
        ))

    fees = [t for t in exp if _match(t, FEES)]
    if fees:
        s = sum(_ron(t) for t in fees)
        recs.append(_rec(
            "fees", "🏦", L("Comisioane bancare", "Bank fees"), "low",
            L(f"Plătești {f(s)} comisioane, adică {f(s * 12)} pe an, pe care le-ai putea evita.",
              f"You pay {f(s)} in fees, that's {f(s * 12)} a year you could avoid."),
            s,
            L(["Cere băncii pachetul fără comision de administrare (multe îl oferă pentru încasare salariu).",
               "Sau mută-ți cheltuielile zilnice pe un cont digital gratuit."],
              ["Ask your bank for the no-fee package (many offer it if your salary lands there).",
               "Or move everyday spending to a free digital account."]),
        ))

    shopping = by_cat.get("Shopping", [])
    if shopping:
        s = sum(_ron(t) for t in shopping)
        top = max(shopping, key=_ron)
        recs.append(_rec(
            "shopping", "🛍️", L("Cumpărături impulsive", "Impulse shopping"), "high" if s > 0.15 * max(E, 1) else "medium",
            L(f"Shopping: {f(s)}, din care cea mai mare plată a fost {merchant_name(top['description'])} ({f(_ron(top))}).",
              f"Shopping: {f(s)}, the biggest being {merchant_name(top['description'])} ({f(_ron(top))})."),
            s * 0.2,
            L(["Aplică regula celor 48 de ore: pune produsul în coș și decide abia după 2 zile.",
               "Pentru electronice, urmărește istoricul de preț. Reducerile reale apar de Black Friday sau la lansarea modelului nou.",
               "Setează un buget lunar de shopping și ține-l pe un card separat."],
              ["Use the 48-hour rule: leave it in the cart and decide two days later.",
               "For electronics, track the price history. Real discounts come on Black Friday or when the new model launches.",
               "Set a monthly shopping budget and keep it on a separate card."]),
        ))

    groc = [t for t in exp if _match(t, GROCERIES)]
    if groc:
        s = sum(_ron(t) for t in groc)
        recs.append(_rec(
            "groceries", "🛒", L("Cumpărături de alimente", "Groceries"), "low",
            L(f"{len(groc)} drumuri la supermarket, total {f(s)} (media {f(s / len(groc))} pe drum).",
              f"{len(groc)} supermarket trips, {f(s)} in total ({f(s / len(groc))} per trip)."),
            s * 0.1,
            L(["Fă lista înainte și mergi o dată pe săptămână: fiecare drum în plus aduce produse neplanificate.",
               "Alege mărcile proprii ale magazinului (cu 20–30% mai ieftine) și urmărește catalogul săptămânal.",
               "Nu face cumpărături când ți-e foame. Sună a clișeu, dar funcționează."],
              ["Write a list and shop once a week: every extra trip brings unplanned items.",
               "Pick store brands (20–30% cheaper) and check the weekly flyer.",
               "Never shop hungry. It's a cliché because it works."]),
        ))

    util = by_cat.get("Utilități", [])
    if util:
        s = sum(_ron(t) for t in util)
        recs.append(_rec(
            "util", "💡", L("Utilități", "Utilities"), "low",
            L(f"Facturile de utilități: {f(s)} în {period}.", f"Utility bills: {f(s)} in {period}."),
            s * 0.08,
            L(["Becuri LED și prize cu întrerupător pentru aparatele în standby (5–10% din factură).",
               "Compară anual furnizorul de energie pe comparatorul ANRE.",
               "Spală la 30°C și pornește mașina de vase doar plină."],
              ["LED bulbs and switchable power strips for standby devices (5–10% off the bill).",
               "Compare energy suppliers every year on the regulator's comparison tool.",
               "Wash at 30°C and only run the dishwasher when it's full."]),
        ))

    if foreign:
        s = sum(_ron(t) for t in foreign)
        recs.append(_rec(
            "fx", "💱", L("Plăți în valută", "Foreign-currency payments"), "low",
            L(f"Ai plătit {f(s)} în altă monedă decât RON.", f"You paid {f(s)} in a currency other than RON."),
            s * 0.02,
            L(["La POS sau online alege plata în moneda locală a comerciantului, nu în RON (evită conversia dinamică DCC).",
               "Folosește un card fără comision de conversie pentru călătorii."],
              ["At the terminal or online, pay in the merchant's local currency, not RON (avoid dynamic currency conversion).",
               "Use a card with no FX fees when travelling."]),
        ))

    if I > 0 and savings / I < 0.2:
        recs.append(_rec(
            "save", "🐷", L("Plătește-te pe tine primul", "Pay yourself first"), "high",
            L("Nu ai încă un obicei automat de economisire.", "You don't have an automatic saving habit yet."),
            I * 0.1 if savings > 0 else 0,
            L(["Setează un transfer automat de 10% din salariu într-un cont de economii, chiar în ziua salariului.",
               "Construiește un fond de urgență de 3–6 luni de cheltuieli înainte de investiții.",
               "Rotunjește plățile cu cardul și trimite diferența automat în economii (funcție oferită de multe bănci)."],
              ["Set up an automatic 10% transfer to savings on payday.",
               "Build a 3–6 month emergency fund before investing.",
               "Turn on card round-ups that send the spare change to savings (many banks offer it)."]),
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
    score -= 6 if big and E and _ron(big) / E >= 0.15 else 0
    score = max(5, min(100, score))
    level = "great" if score >= 80 else "good" if score >= 60 else "watch" if score >= 40 else "critical"
    label = {"great": L("Excelent", "Excellent"), "good": L("Bun", "Good"),
             "watch": L("Atenție", "Watch out"), "critical": L("Critic", "Critical")}[level]

    # ------------------------------------------------------------ tabel calitativ categorii
    cat_table = []
    for cat_name, items in sorted(((k, v) for k, v in by_cat.items() if v), key=lambda kv: -sum(_ron(t) for t in kv[1])):
        s = sum(_ron(t) for t in items)
        budget = I * BUDGET_SHARE.get(cat_name, 5) / 100 if I else 0
        ratio = s / budget if budget else 0
        status = ("ok" if ratio <= 1 else "warn" if ratio <= 1.25 else "over") if budget else "na"
        cat_table.append({
            "category": cat_name, "label": i18n.cat(cat_name, lang), "total": c(s),
            "share": round(s / E * 100, 1) if E else 0, "count": len(items), "avg": c(s / len(items)),
            "max": c(max(_ron(t) for t in items)), "budget": c(budget), "budget_pct": BUDGET_SHARE.get(cat_name, 5),
            "usage": round(ratio * 100), "status": status,
        })

    # ------------------------------------------------------------ comercianți & abonamente
    merch: dict[str, list[dict]] = defaultdict(list)
    for t in exp:
        merch[merchant_name(t["description"])].append(t)
    merchants = sorted(({
        "name": n, "category": items[0]["category"], "label": i18n.cat(items[0]["category"], lang),
        "visits": len(items), "total": c(sum(_ron(t) for t in items)),
        "avg": c(sum(_ron(t) for t in items) / len(items)), "last": max(t["date"] for t in items),
    } for n, items in merch.items()), key=lambda m: -m["total"])

    subs_table = [{
        "name": merchant_name(t["description"]), "monthly": c(_ron(t)), "yearly": c(_ron(t) * 12),
        "category": t["category"],
        "tip": L("Verifică dacă îl folosești săptămânal", "Check you use it weekly") if _match(t, STREAMING)
        else L("Cere oferta de fidelizare", "Ask for the loyalty offer"),
    } for t in subs]

    return {
        "lang": lang, "period": period, "currency": cur,
        "totals": {"expenses": c(E), "income": c(I), "net": c(savings),
                   "savings_rate": round(savings / I * 100, 1) if I else None,
                   "count": len(exp), "avg_tx": c(E / len(exp)) if exp else 0},
        "score": score, "score_level": level, "score_label": label,
        "rule_50_30_20": {"needs": c(needs), "wants": c(wants), "savings": c(max(savings, 0)), "income": c(I),
                          "needs_pct": round(needs / I * 100) if I else 0,
                          "wants_pct": round(wants / I * 100) if I else 0,
                          "savings_pct": round(max(savings, 0) / I * 100) if I else 0},
        "alerts": alerts, "recommendations": recs,
        "potential_saving": c(potential), "potential_saving_year": c(potential * 12),
        "categories": cat_table, "merchants": merchants[:12], "subscriptions": subs_table,
        "personality": _personality(exp, by_cat, E, I, eating_sum, len(subs), L),
        "budgets": _budgets(by_cat, budgets or {}, rows, month, I, c, f, L, lang),
        "headline": _headline(period, E, I, potential, recs, f, L),
    }


def suggest_budgets(txs: list[dict], month: str) -> dict[str, float]:
    """Buget recomandat (RON): procentul orientativ din venit; fără venit, cheltuiala lunii minus 10%."""
    rows = [t for t in txs if not month or t["date"].startswith(month)]
    months = max(len({t["date"][:7] for t in rows}), 1)
    income = sum(_ron(t) for t in rows if t["direction"] == "credit") / months
    spent: dict[str, float] = defaultdict(float)
    for t in rows:
        if t["direction"] == "debit" and t["category"] != "Venituri":
            spent[t["category"]] += _ron(t) / months
    out = {}
    for cat_name, share in BUDGET_SHARE.items():
        v = income * share / 100 if income else spent.get(cat_name, 0) * 0.9
        if v > 0:
            out[cat_name] = max(50.0, round(v / 50) * 50)  # rotunjit la 50 RON, ca un buget real
    return out


def _budgets(by_cat, budgets, rows, month, I, c, f, L, lang) -> dict:
    """Bugete vs. cheltuieli: depășite (deficit), respectate (surplus), nesetate."""
    months = 1 if month else max(len({t["date"][:7] for t in rows}), 1)
    items = []
    for cat_name in BUDGET_SHARE:  # toate categoriile de cheltuieli, în ordinea fixă
        spent = sum(_ron(t) for t in by_cat.get(cat_name, []))
        budget = budgets.get(cat_name, 0) * months
        name = i18n.cat(cat_name, lang)
        if not budget:
            status, diff = "unset", 0.0
            text = (L(f"Ai cheltuit {f(spent)} pe {name} fără un buget. Setează unul ca să-ți urmăresc limita.",
                      f"You spent {f(spent)} on {name} without a budget. Set one and I'll keep watch.")
                    if spent else L("Nicio cheltuială și niciun buget setat.", "No spending and no budget set."))
        elif spent > budget:
            status, diff = "over", spent - budget
            nxt = budget - diff
            text = L("Încearcă să recuperezi deficitul cheltuind mai puțin. ", "Try to recover the deficit by spending less. ") + (
                L(f"Luna viitoare țintește cel mult {f(nxt)} pe {name}.", f"Next month, aim for at most {f(nxt)} on {name}.") if nxt > 0
                else L(f"Deficitul depășește un buget întreg: amână cheltuielile neesențiale pe {name}.",
                       f"The deficit exceeds a whole budget: postpone non-essential {name} spending."))
        else:
            diff = budget - spent
            status = "near" if spent >= 0.85 * budget else "ok"
            text = (L(f"Ești aproape de limită: mai ai doar {f(diff)} din buget.", f"Close to the limit: only {f(diff)} left in the budget.")
                    if status == "near" else
                    L(f"Bravo! Ai rămas sub buget cu {f(diff)}.", f"Well done! You stayed {f(diff)} under budget."))
        items.append({
            "category": cat_name, "label": name, "status": status, "spent": c(spent), "budget": c(budget), "diff": c(diff),
            "usage": round(spent / budget * 100) if budget else None, "text": text,
        })
    order = {"over": 0, "near": 1, "ok": 2, "unset": 3}
    items.sort(key=lambda b: (order[b["status"]], -b["diff"] if b["status"] == "over" else -b["spent"]))
    counts = {"over": sum(b["status"] == "over" for b in items),
              "ok": sum(b["status"] in ("ok", "near") for b in items),
              "unset": sum(b["status"] == "unset" for b in items)}
    return {"items": items, "counts": counts, "months": months,
            "total_budget": c(sum(budgets.values()) * months), "has_any": bool(budgets)}


def _personality(exp, by_cat, E, I, eating_sum, n_subs, L) -> dict:
    """Arhetipul lunii: o etichetă jucăușă, dar calculată din cifre reale."""
    if not exp:
        return {"id": "fresh", "emoji": "🌱", "title": L("Pagina albă", "The Fresh Start"),
                "text": L("Încă nu am destule date despre tine.", "I don't know you well enough yet.")}
    share = lambda cats: sum(_ron(t) for c_ in cats for t in by_cat.get(c_, [])) / E  # noqa: E731
    weekend = sum(_ron(t) for t in exp if date.fromisoformat(t["date"]).weekday() >= 5) / E
    candidates = [
        (share(["Călătorii"]) >= 0.08, "explorer", "🧭", L("Exploratorul", "The Explorer"),
         L("Banii tăi au pașaport: călătoriile au o felie serioasă din buget.", "Your money has a passport: travel takes a real slice of the budget.")),
        (eating_sum / E >= 0.06 or share(["Mâncare"]) >= 0.2, "foodie", "🍜", L("Gurmandul", "The Foodie"),
         L("Mâncarea bună e prioritatea ta, de la livrări la restaurante.", "Good food is your priority, from deliveries to restaurants.")),
        (share(["Shopping"]) >= 0.15, "hunter", "🛍️", L("Vânătorul de oferte", "The Deal Hunter"),
         L("Coșul de cumpărături se umple ușor; o regulă de 48 de ore te-ar ajuta.", "Your cart fills up fast; a 48-hour rule would help.")),
        (weekend >= 0.45, "weekend", "🎉", L("Starul de weekend", "The Weekend Star"),
         L("Aproape jumătate din bani pleacă sâmbăta și duminica.", "Almost half your money goes out on weekends.")),
        (n_subs >= 3, "streamer", "📺", L("Maratonistul de seriale", "The Binge Watcher"),
         L("Ai o colecție frumoasă de abonamente.", "You've got quite a subscription collection.")),
        (I > 0 and (I - E) / I >= 0.2, "saver", "🐿️", L("Veverița prevăzătoare", "The Squirrel Saver"),
         L("Pui deoparte constant. Respect!", "You save consistently. Respect!")),
    ]
    for ok, pid, emoji, title, text in candidates:
        if ok:
            return {"id": pid, "emoji": emoji, "title": title, "text": text}
    return {"id": "balanced", "emoji": "⚖️", "title": L("Echilibristul", "The Balancer"),
            "text": L("Cheltuielile tale sunt împărțite destul de echilibrat.", "Your spending is nicely balanced.")}


def _headline(period, E, I, potential, recs, f, L) -> str:
    if not E and not I:
        return L("Încarcă un fișier și îți spun imediat unde îți zboară banii.",
                 "Upload a file and I'll show you right away where your money goes.")
    s = L(f"În {period} ai cheltuit {f(E)}", f"In {period} you spent {f(E)}")
    if I:
        s += L(f" și ai încasat {f(I)}", f" and earned {f(I)}")
    s += "."
    if recs:
        s += L(f" Am găsit {len(recs)} idei prin care poți economisi aproximativ {f(potential)} pe lună.",
               f" I found {len(recs)} ideas that could save you about {f(potential)} a month.")
    return s


def _alert(level: str, title: str, text: str) -> dict:
    return {"level": level, "title": title, "text": text}


def _rec(rid, icon, title, priority, text, saving_ron, tips) -> dict:
    return {"id": rid, "icon": icon, "title": title, "priority": priority, "text": text,
            "saving_ron": round(max(saving_ron, 0), 2), "tips": tips}


def summary_for_ai(ins: dict) -> dict:
    """Doar totaluri agregate, fără nicio tranzacție individuală."""
    return {
        "perioada": ins["period"], "moneda": ins["currency"], "totaluri": ins["totals"],
        "scor": ins["score"], "regula_50_30_20": ins["rule_50_30_20"],
        "categorii": [{k: r[k] for k in ("category", "total", "share", "count", "usage")} for r in ins["categories"]],
        "top_comercianti": [{k: m[k] for k in ("name", "visits", "total")} for m in ins["merchants"][:8]],
        "abonamente": [s["name"] for s in ins["subscriptions"]],
    }
