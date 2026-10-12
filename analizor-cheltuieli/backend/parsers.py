"""Parsare deterministă (fără AI) pentru CSV-ul de card și extrasul PDF.

Tot ce se poate face cu reguli clare se face aici, gratuit și reproductibil.
AI-ul intervine doar unde chiar e nevoie (categorii, bonuri foto).
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date

MONEDE = ("RON", "EUR", "USD")

LUNI_RO = {
    "ian": 1, "feb": 2, "mar": 3, "apr": 4, "mai": 5, "iun": 6,
    "iul": 7, "aug": 8, "sep": 9, "oct": 10, "noi": 11, "nov": 11, "dec": 12,
}


class ParseError(ValueError):
    pass


# ---------------------------------------------------------------- date & sume

def parse_date(text: str) -> date | None:
    """Acceptă: 2026-03-04, 05/03/2026, 6.03.2026, 3 mar. 2026, 21-03-2026."""
    if not text:
        return None
    s = text.strip().lower()

    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return _safe_date(y, mo, d)

    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
    if m:  # format românesc: zi/lună/an
        d, mo, y = map(int, m.groups())
        return _safe_date(y, mo, d)

    m = re.fullmatch(r"(\d{1,2})\s+([a-zăâîșşțţ]+)\.?\s+(\d{4})", s)
    if m:
        d, luna, y = m.groups()
        mo = LUNI_RO.get(luna[:3])
        if mo:
            return _safe_date(int(y), mo, int(d))
    return None


def _safe_date(y: int, mo: int, d: int) -> date | None:
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_amount(text: str) -> float | None:
    """Acceptă: 1.249,99 · 1249,99 · 1,249.99 · 1249.99 · -59,99 · '87,45 RON'."""
    if text is None:
        return None
    s = re.sub(r"[^\d,.\-]", "", str(text).strip())
    if not s or not re.search(r"\d", s):
        return None
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "," in s and "." in s:
        # separatorul zecimal e cel care apare ultimul
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", s):  # 1,249 = mii
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s and re.fullmatch(r"\d{1,3}(\.\d{3})+", s):  # 1.249 = mii
        s = s.replace(".", "")
    try:
        v = round(float(s), 2)
    except ValueError:
        return None
    return -v if neg else v


def detect_currency(text: str, default: str = "RON") -> str:
    t = (text or "").upper()
    if "EUR" in t or "€" in t:
        return "EUR"
    if "USD" in t or "$" in t:
        return "USD"
    if "RON" in t or "LEI" in t:
        return "RON"
    return default


def _tx(d: date, desc: str, amount: float, currency: str, direction: str, source: str) -> dict:
    return {
        "date": d.isoformat(),
        "description": re.sub(r"\s+", " ", desc).strip(),
        "amount": round(abs(amount), 2),
        "currency": currency,
        "direction": direction,  # "debit" (ieșire) sau "credit" (intrare)
        "source": source,
    }


# ---------------------------------------------------------------- CSV card

_HEADER_HINTS = {
    "date": ("data", "date"),
    "desc": ("descriere", "detalii", "description", "beneficiar", "comerciant"),
    "debit": ("debit",),
    "credit": ("credit",),
    "amount": ("suma", "sumă", "amount", "valoare"),
    "currency": ("moneda", "monedă", "valuta", "currency"),
}


def _find_col(header: list[str], key: str) -> int | None:
    for i, h in enumerate(header):
        h = h.strip().lower()
        if any(h.startswith(x) or x in h for x in _HEADER_HINTS[key]):
            return i
    return None


def parse_card_csv(raw: bytes) -> tuple[list[dict], list[str]]:
    text = _decode(raw)
    lines = text.splitlines()
    delim = _sniff_delimiter(lines)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))

    # antetul real poate fi după câteva rânduri de titlu
    header_idx = None
    for i, r in enumerate(rows[:30]):
        low = [c.strip().lower() for c in r]
        if any(c.startswith("data") or c == "date" for c in low) and (
            any("debit" in c or "credit" in c or "suma" in c or "amount" in c for c in low)
        ):
            header_idx = i
            break
    if header_idx is None:
        raise ParseError("Nu am găsit rândul de antet (Data / Descriere / Debit / Credit) în CSV.")

    header = rows[header_idx]
    c_date, c_desc = _find_col(header, "date"), _find_col(header, "desc")
    c_deb, c_cred = _find_col(header, "debit"), _find_col(header, "credit")
    c_amt, c_cur = _find_col(header, "amount"), _find_col(header, "currency")
    if c_date is None or c_desc is None or (c_deb is None and c_cred is None and c_amt is None):
        raise ParseError("CSV-ul nu are coloanele necesare (dată, descriere, sumă).")

    txs, warnings = [], []
    for n, r in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not any(c.strip() for c in r):
            continue
        get = lambda i: r[i].strip() if i is not None and i < len(r) else ""
        d = parse_date(get(c_date))
        if d is None:
            # rânduri de subsol tip "Total inregistrari: 24" – ignorate intenționat
            if get(c_date) and not get(c_date).lower().startswith("total"):
                warnings.append(f"Rândul {n}: dată nerecunoscută „{get(c_date)}”, ignorat.")
            continue
        currency = detect_currency(get(c_cur)) if c_cur is not None else "RON"
        deb, cred = parse_amount(get(c_deb)), parse_amount(get(c_cred))
        if deb is None and cred is None and c_amt is not None:
            v = parse_amount(get(c_amt))
            if v is not None:
                deb, cred = (abs(v), None) if v < 0 else (None, v)
        if deb:
            txs.append(_tx(d, get(c_desc), deb, currency, "debit", "card_csv"))
        elif cred:
            txs.append(_tx(d, get(c_desc), cred, currency, "credit", "card_csv"))
        else:
            warnings.append(f"Rândul {n}: fără sumă, ignorat.")
    return txs, warnings


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _sniff_delimiter(lines: list[str]) -> str:
    sample = [l for l in lines[:40] if l.strip()]
    best, best_score = ";", -1
    for d in (";", ",", "\t", "|"):
        score = sum(l.count(d) for l in sample)
        if score > best_score:
            best, best_score = d, score
    return best


# ---------------------------------------------------------------- extras PDF

_AMT = r"-?\d{1,3}(?:[.\s]\d{3})*,\d{2}|-?\d+,\d{2}|-?\d{1,3}(?:,\d{3})*\.\d{2}|-?\d+\.\d{2}"
_PDF_LINE = re.compile(
    rf"^(?P<date>\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})\s+(?P<rest>.+?)\s*$"
)


def parse_statement_pdf(raw: bytes) -> tuple[list[dict], list[str]]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    if not text.strip():
        raise ParseError("PDF-ul nu conține text (probabil e scanat).")

    m = re.search(r"Moned[aă]\s*:\s*([A-Z]{3})", text)
    currency = m.group(1) if m and m.group(1) in MONEDE else detect_currency(text)

    txs, warnings = [], []
    prev_balance = None
    for line in text.splitlines():
        lm = _PDF_LINE.match(line.strip())
        if not lm:
            continue
        d = parse_date(lm.group("date"))
        rest = lm.group("rest")
        amounts = list(re.finditer(_AMT, rest))
        if not amounts or d is None:
            continue
        desc = rest[: amounts[0].start()].strip()
        values = [parse_amount(a.group()) for a in amounts]
        low = desc.lower()

        if low.startswith("sold"):  # sold inițial / final – nu e tranzacție
            prev_balance = values[-1]
            continue

        if len(values) >= 2:
            amount, balance = values[-2], values[-1]
            # Debit sau credit? Îl deducem din variația soldului: robust indiferent
            # de coloana în care a pus pdf-ul suma.
            if prev_balance is not None:
                delta = round(balance - prev_balance, 2)
                direction = "credit" if delta > 0 else "debit"
                if abs(abs(delta) - abs(amount)) > 0.01:
                    warnings.append(
                        f"{d.isoformat()} {desc}: suma {amount} nu se potrivește cu variația soldului ({delta})."
                    )
            else:
                direction = "credit" if _looks_like_income(low) else "debit"
            prev_balance = balance
        else:
            amount = values[0]
            direction = "credit" if _looks_like_income(low) else "debit"
        txs.append(_tx(d, desc, amount, currency, direction, "extras_pdf"))
    return txs, warnings


def _looks_like_income(low: str) -> bool:
    return any(k in low for k in ("incasare", "încasare", "salariu", "dobanda", "dobândă", "transfer primit", "rambursare"))


# ---------------------------------------------------------------- titularul contului

_HOLDER = re.compile(r"Titular\s*:\s*([A-Za-zĂÂÎȘŞȚŢăâîșşțţ][A-Za-zĂÂÎȘŞȚŢăâîșşțţ.\- ]{1,60}?)\s*(?:[;|,\n]|$)", re.M)


def extract_holder(raw: bytes, ext: str) -> str | None:
    """Numele titularului din antetul extrasului („Titular: MATEI IONESCU”), pentru salutul personalizat."""
    try:
        if ext == ".pdf":
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                text = (pdf.pages[0].extract_text() or "") if pdf.pages else ""
        else:
            text = _decode(raw[:4000])
    except Exception:  # noqa: BLE001 – numele e opțional, nu blocăm upload-ul
        return None
    m = _HOLDER.search(text)
    return m.group(1).strip().title() if m else None
