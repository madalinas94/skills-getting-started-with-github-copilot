"""Suport bilingv (română / engleză) pentru textele generate de server.

Categoriile rămân stocate cu ID-ul românesc (lista fixă din enunț); doar
afișarea se traduce.
"""
from __future__ import annotations

LANGS = ("ro", "en")

CAT_EN = {
    "Mâncare": "Food", "Transport": "Transport", "Utilități": "Utilities", "Locuință": "Housing",
    "Sănătate": "Health", "Divertisment": "Entertainment", "Shopping": "Shopping", "Călătorii": "Travel",
    "Venituri": "Income", "Altele": "Other",
}
MONTHS = {
    "ro": ["", "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
           "septembrie", "octombrie", "noiembrie", "decembrie"],
    "en": ["", "January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
}


def norm(lang: str | None) -> str:
    return lang if lang in LANGS else "ro"


def pick(lang: str, ro: str, en: str) -> str:
    return en if lang == "en" else ro


def cat(name: str, lang: str) -> str:
    return CAT_EN.get(name, name) if lang == "en" else name


def month_label(ym: str, lang: str = "ro") -> str:
    y, m = ym.split("-")
    return f"{MONTHS[norm(lang)][int(m)]} {y}"


def fmt(v: float, cur: str, lang: str = "ro") -> str:
    s = f"{abs(v):,.2f}"
    if lang != "en":
        s = s.replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{'-' if v < 0 else ''}{s} {cur}"


def date_label(iso: str, lang: str = "ro") -> str:
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS[norm(lang)][int(m)][:3]}" if lang == "en" else f"{d}.{m}.{y}"
