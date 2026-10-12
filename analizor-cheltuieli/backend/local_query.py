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
_CAT_WORDS = {
    "Mâncare": ["mancare", "alimente", "mancat", "restaurant", "supermarket", "food", "cumparaturi alimentare"],
    "Transport": ["transport", "benzina", "carburant", "taxi", "uber", "bolt", "masina"],
    "Utilități": ["utilitati", "facturi", "curent", "internet", "gaz"],
    "Locuință": ["locuinta", "chirie"],
    "Sănătate": ["sanatate", "farmacie", "medicamente", "doctor"],
    "Divertisment": ["divertisment", "distractie", "abonamente", "netflix", "cinema", "streaming"],
    "Shopping": ["shopping", "haine", "electronice", "cumparaturi online"],
    "Călătorii": ["calatorii", "vacanta", "hotel", "calatorie"],
    "Venituri": [],
    "Altele": ["altele", "comisioane"],
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
    if re.search(r"incasa|castig|venit|salariu|primit", s):
        q["tip"] = "venituri"
    if re.search(r"\bcate\b|numar", s):
        q["operatie"] = "numar"
    elif re.search(r"medie|in medie", s):
        q["operatie"] = "medie"
    elif re.search(r"cea mai mare|cel mai mare|cea mai scumpa|maxim", s):
        q["operatie"] = "maxim"
    elif re.search(r"categori|distributi|pe ce", s):
        q["operatie"] = "pe_categorii"
    elif re.search(r"magazin|comerciant|unde", s):
        q["operatie"] = "pe_comercianti"
    elif re.search(r"\b(arata|lista|care|ce tranzactii)\b", s):
        q["operatie"] = "lista"
    m = re.search(r"\btop\s*(\d+)", s)
    if m:
        q["limita"] = int(m.group(1))

    for cat, words in _CAT_WORDS.items():
        if any(re.search(rf"\b{w}", s) for w in words):
            q["categorii"].append(cat)

    for num, pattern in enumerate(_MONTHS, start=1):
        if re.search(pattern, s):
            ym = [x for x in months if int(x[5:]) == num]
            year = re.search(r"\b(20\d\d)\b", s)
            q["luna"] = f"{year.group(1)}-{num:02d}" if year else (ym[-1] if ym else "")
            break

    if re.search(r"\bin (euro|eur)\b|euro\b", s):
        key = "moneda_originala" if "facut" in s or "platit in" in s or "tranzacti" in s else "moneda_afisare"
        q[key] = "EUR"
    if re.search(r"dolari|\busd\b", s):
        q["moneda_afisare"] = "USD"
    if re.search(r"\blei\b|\bron\b", s):
        q["moneda_afisare"] = "RON"
    m = re.search(r"\b(?:la|de la)\s+([a-z0-9][a-z0-9.\- ]{2,20}?)(?:\s+(?:in|pe|din)\b|[?.!]|$)", s)
    if m and not q["categorii"]:
        q["text_cautat"] = m.group(1).strip()
    if re.search(r"cash|numerar|bon", s):
        q["surse"] = ["bon"]
    q["interpretare"] = ""
    return q
