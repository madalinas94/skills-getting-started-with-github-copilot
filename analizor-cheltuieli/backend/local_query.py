"""Interpretare locală (fără AI) a întrebărilor – folosită doar ca rezervă
când API-ul Claude nu e disponibil. Acoperă formulările uzuale."""
from __future__ import annotations

import re
import unicodedata

# „mai” e și adverb („cea mai mare”), deci îl acceptăm doar după „în/luna/din”.
_MONTHS = [
    r"\bianuarie\b|\bian\b", r"\bfebruarie\b|\bfeb\b", r"\bmartie\b|\bmar\b", r"\baprilie\b|\bapr\b",
    r"\b(in|luna|din) mai\b", r"\biunie\b|\biun\b", r"\biulie\b|\biul\b", r"\baugust\b|\baug\b",
    r"\bseptembrie\b|\bsept?\b", r"\boctombrie\b|\boct\b", r"\bnoiembrie\b", r"\bdecembrie\b|\bdec\b",
]
# lunile în engleză („may” e lună doar după „in”)
_MONTHS_EN = [
    r"\bjanuary\b", r"\bfebruary\b", r"\bmarch\b", r"\bapril\b", r"\bin may\b", r"\bjune\b", r"\bjuly\b",
    r"\baugust\b", r"\bseptember\b", r"\boctober\b", r"\bnovember\b", r"\bdecember\b",
]
_CAT_WORDS = {
    "Mâncare": ["mancare", "alimente", "mancat", "restaurant", "supermarket", "food", "cumparaturi alimentare",
                "groceries", "eating", "dining"],
    "Transport": ["transport", "benzina", "carburant", "taxi", "uber", "bolt", "masina", "fuel", "petrol", "gas\\b", "car\\b"],
    "Utilități": ["utilitati", "facturi", "curent", "internet", "gaz\\b", "utilities", "bills", "electricity"],
    "Locuință": ["locuinta", "chirie", "rent", "housing"],
    "Sănătate": ["sanatate", "farmacie", "medicamente", "doctor", "health", "pharmacy"],
    "Divertisment": ["divertisment", "distractie", "abonamente", "netflix", "cinema", "streaming", "entertainment", "fun\\b"],
    "Shopping": ["shopping", "haine", "electronice", "cumparaturi online", "clothes"],
    "Călătorii": ["calatorii", "vacanta", "hotel", "calatorie", "travel", "holiday", "trip"],
    "Venituri": [],
    "Altele": ["altele", "comisioane", "fees"],
}


def _strip(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def parse(question: str, months: list[str]) -> dict:
    s = _strip(question)
    q = {
        "operatie": "suma", "tip": "cheltuieli", "categorii": [], "luna": "",
        "data_de_la": "", "data_pana_la": "", "text_cautat": "", "surse": [],
        "moneda_originala": "", "moneda_afisare": "", "limita": 0,
        "interpretare": "", "in_afara_domeniului": False,
    }
    if re.search(r"incasa|castig|venit|salariu|primit|income|earn|salary|received", s):
        q["tip"] = "venituri"
    if re.search(r"\bcate\b|numar|how many|count", s):
        q["operatie"] = "numar"
    elif re.search(r"medie|in medie|average", s):
        q["operatie"] = "medie"
    elif re.search(r"cea mai mare|cel mai mare|cea mai scumpa|maxim|biggest|largest|most expensive", s):
        q["operatie"] = "maxim"
    elif re.search(r"categor|distributi|pe ce|breakdown", s):
        q["operatie"] = "pe_categorii"
    elif re.search(r"magazin|comerciant|unde|merchant|store|shops?\b|where", s):
        q["operatie"] = "pe_comercianti"
    elif re.search(r"\b(arata|lista|care|ce tranzactii|show|list|which)\b", s):
        q["operatie"] = "lista"
    m = re.search(r"\btop\s*(\d+)", s)
    if m:
        q["limita"] = int(m.group(1))

    for cat, words in _CAT_WORDS.items():
        if any(re.search(rf"\b{w}", s) for w in words):
            q["categorii"].append(cat)

    for num, (pattern, pattern_en) in enumerate(zip(_MONTHS, _MONTHS_EN), start=1):
        if re.search(pattern, s) or re.search(pattern_en, s):
            ym = [x for x in months if int(x[5:]) == num]
            year = re.search(r"\b(20\d\d)\b", s)
            q["luna"] = f"{year.group(1)}-{num:02d}" if year else (ym[-1] if ym else "")
            break

    if re.search(r"\bin (euro|eur)\b|euros?\b", s):
        key = ("moneda_originala" if re.search(r"facut|platit in|tranzacti|transactions?|made|paid in", s)
               else "moneda_afisare")
        q[key] = "EUR"
    if re.search(r"dolari|dollars?|\busd\b", s):
        q["moneda_afisare"] = "USD"
    if re.search(r"\blei\b|\bron\b", s):
        q["moneda_afisare"] = "RON"
    m = re.search(r"\b(?:la|de la|at)\s+([a-z0-9][a-z0-9.\- ]{2,20}?)(?:\s+(?:in|pe|din|on)\b|[?.!]|$)", s)
    if m and not q["categorii"]:
        q["text_cautat"] = m.group(1).strip()
    if re.search(r"cash|numerar|\bbon|receipt", s):
        q["surse"] = ["bon"]
    q["interpretare"] = ""
    return q
