"""Stocarea tranzacțiilor, deduplicarea între surse și motorul de calcul."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from collections import defaultdict
from datetime import date
from pathlib import Path

from .categorize import normalize_key

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "tranzactii.json"

# Cursuri fixe din enunț: câți RON valorează o unitate din moneda respectivă.
RATES = {"RON": 1.0, "EUR": 5.25, "USD": 4.40}

LUNI_NUME = ["", "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie",
             "august", "septembrie", "octombrie", "noiembrie", "decembrie"]

SOURCE_LABEL = {"card_csv": "Card (CSV)", "extras_pdf": "Extras (PDF)", "bon": "Bon numerar"}


def convert(amount: float, frm: str, to: str) -> float:
    return amount * RATES[frm] / RATES[to]


def fmt(v: float, cur: str) -> str:
    s = f"{abs(v):,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{'-' if v < 0 else ''}{s} {cur}"


def month_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{LUNI_NUME[int(m)]} {y}"


class Store:
    def __init__(self, path: Path = DATA_FILE):
        self.path = path
        self.lock = threading.Lock()
        self.txs: list[dict] = []
        self.files: dict[str, str] = {}  # hash -> nume fișier
        self._load()

    # ------------------------------------------------------------ persistență
    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.txs, self.files = data.get("txs", []), data.get("files", {})
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"txs": self.txs, "files": self.files}, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    @staticmethod
    def file_hash(raw: bytes) -> str:
        return hashlib.sha256(raw).hexdigest()

    def seen_file(self, h: str) -> str | None:
        return self.files.get(h)

    # ------------------------------------------------------------ modificări
    def add(self, txs: list[dict], file_name: str, file_hash: str | None) -> list[dict]:
        with self.lock:
            for tx in txs:
                tx["id"] = uuid.uuid4().hex[:10]
                tx["file"] = file_name
                tx.setdefault("duplicate_of", None)
            self.txs.extend(txs)
            if file_hash:
                self.files[file_hash] = file_name
            self._mark_duplicates()
            self._save()
        return txs

    def update(self, tx_id: str, **fields) -> dict | None:
        with self.lock:
            for tx in self.txs:
                if tx["id"] == tx_id:
                    tx.update(fields)
                    self._save()
                    return tx
        return None

    def delete(self, tx_id: str) -> bool:
        with self.lock:
            n = len(self.txs)
            self.txs = [t for t in self.txs if t["id"] != tx_id]
            self._mark_duplicates()
            self._save()
            return len(self.txs) < n

    def reset(self) -> None:
        with self.lock:
            self.txs, self.files = [], {}
            self._save()

    # ------------------------------------------------------------ deduplicare
    def _mark_duplicates(self) -> None:
        """O plată cu cardul apare și în CSV-ul cardului, și în extrasul de cont.
        Păstrăm rândul din CSV (descriere mai bună) și marcăm rândul din extras
        ca duplicat, ca să nu fie numărat de două ori la totaluri."""
        for t in self.txs:
            t["duplicate_of"] = None
        card = [t for t in self.txs if t["source"] == "card_csv"]
        used: set[str] = set()
        for t in self.txs:
            if t["source"] != "extras_pdf":
                continue
            best, best_gap = None, 99
            for c in card:
                if c["id"] in used or c["currency"] != t["currency"] or c["direction"] != t["direction"]:
                    continue
                if abs(c["amount"] - t["amount"]) > 0.005:
                    continue
                gap = abs((date.fromisoformat(c["date"]) - date.fromisoformat(t["date"])).days)
                if gap > 3:  # plata cu cardul poate fi decontată cu câteva zile întârziere
                    continue
                same_merchant = _token_overlap(c["description"], t["description"])
                if gap == 0 or same_merchant or "card" in t["description"].lower():
                    if gap < best_gap:
                        best, best_gap = c, gap
            if best:
                t["duplicate_of"] = best["id"]
                used.add(best["id"])

    # ------------------------------------------------------------ interogare
    def months(self) -> list[str]:
        return sorted({t["date"][:7] for t in self.txs})

    def active(self) -> list[dict]:
        return [t for t in self.txs if not t.get("duplicate_of")]

    def run_query(self, q: dict, display_currency: str = "RON") -> dict:
        cur = q.get("moneda_afisare") or display_currency or "RON"
        rows = self.filter(q)
        op = q.get("operatie", "suma")
        tip = q.get("tip", "cheltuieli")
        conv = lambda t: convert(t["amount"], t["currency"], cur)
        total = round(sum(conv(t) for t in rows), 2)
        limit = q.get("limita") or 0

        result: dict = {"currency": cur, "count": len(rows), "total": total,
                        "ids": [t["id"] for t in rows], "breakdown": []}
        if op in ("pe_categorii", "pe_comercianti"):
            groups: dict[str, float] = defaultdict(float)
            for t in rows:
                k = t["category"] if op == "pe_categorii" else _merchant(t["description"])
                groups[k] += conv(t)
            items = sorted(groups.items(), key=lambda kv: -kv[1])
            if limit:
                items = items[:limit]
            result["breakdown"] = [{"label": k, "value": round(v, 2)} for k, v in items]
        if op == "maxim" and rows:
            top = sorted(rows, key=conv, reverse=True)[: max(limit, 1)]
            result["ids"] = [t["id"] for t in top]
            result["top"] = top
        if op == "lista" and limit:
            result["ids"] = [t["id"] for t in sorted(rows, key=conv, reverse=True)[:limit]]
        result["answer"] = _answer(q, op, tip, rows, result, cur)
        return result

    def filter(self, q: dict) -> list[dict]:
        tip = q.get("tip", "cheltuieli")
        cats = set(q.get("categorii") or [])
        luna = (q.get("luna") or "").strip()
        d_from, d_to = (q.get("data_de_la") or "").strip(), (q.get("data_pana_la") or "").strip()
        text = (q.get("text_cautat") or "").strip().lower()
        surse = set(q.get("surse") or [])
        moneda = q.get("moneda_originala") or ""
        out = []
        for t in self.active():
            if tip == "cheltuieli" and (t["direction"] != "debit" or t["category"] == "Venituri"):
                continue
            if tip == "venituri" and t["direction"] != "credit":
                continue
            if cats and t["category"] not in cats:
                continue
            if luna and not t["date"].startswith(luna):
                continue
            if d_from and t["date"] < d_from:
                continue
            if d_to and t["date"] > d_to:
                continue
            if text and text not in t["description"].lower():
                continue
            if surse and t["source"] not in surse:
                continue
            if moneda and t["currency"] != moneda:
                continue
            out.append(t)
        return sorted(out, key=lambda t: t["date"])


def _token_overlap(a: str, b: str) -> bool:
    ta = {w for w in normalize_key(a).split() if len(w) > 3}
    tb = {w for w in normalize_key(b).split() if len(w) > 3}
    return bool(ta & tb)


_STOP = {"BUCURESTI", "BUC", "SRL", "SA", "SCS", "ROMANIA", "RO", "COM", "HELP", "AFI", "COTROCENI",
         "BANEASA", "AMSTERDAM", "STOCKHOLM", "MUNTENIA", "DISCOUNT", "PLATA", "CARD", "O"}


def merchant_name(desc: str) -> str:
    """„LIDL DISCOUNT 4410 BUCURESTI” -> „Lidl”, „UBER *TRIP HELP.UBER.COM” -> „Uber Trip”."""
    words = [w.strip(".") for w in re.split(r"[\s*/]+", normalize_key(desc))]
    words = [w for w in words if len(w) > 1 and w not in _STOP]
    name = " ".join(words[:2]).title()
    return re.sub(r"\.(Eu|Ro|Com)\b", "", name) or desc


_merchant = merchant_name


def _period(q: dict) -> str:
    if q.get("luna"):
        return f" în {month_label(q['luna'])}"
    if q.get("data_de_la") or q.get("data_pana_la"):
        return f" în perioada {q.get('data_de_la') or '…'} – {q.get('data_pana_la') or '…'}"
    return ""


def _answer(q: dict, op: str, tip: str, rows: list[dict], r: dict, cur: str) -> str:
    cats = q.get("categorii") or []
    what = f" pe {', '.join(cats)}" if cats else ""
    if q.get("text_cautat"):
        what += f" la „{q['text_cautat']}”"
    if q.get("moneda_originala"):
        what += f" (doar tranzacții în {q['moneda_originala']})"
    period = _period(q)
    verb = "ai încasat" if tip == "venituri" else ("ai avut tranzacții de" if tip == "toate" else "ai cheltuit")
    n = len(rows)
    if n == 0:
        return f"Nu am găsit nicio tranzacție{what}{period}."
    plural = "tranzacție" if n == 1 else "tranzacții"
    foreign = {t["currency"] for t in rows} - {cur}
    note = f" Sumele în {', '.join(sorted(foreign))} au fost convertite la cursul fix." if foreign else ""

    if op == "numar":
        return f"Ai {n} {plural}{what}{period}, în valoare totală de {fmt(r['total'], cur)}.{note}"
    if op == "medie":
        return f"În medie, {fmt(r['total'] / n, cur)} per tranzacție{what}{period} ({n} {plural}).{note}"
    if op == "maxim":
        t = r["top"][0]
        return (f"Cea mai mare: {t['description']} pe {t['date']} – "
                f"{fmt(convert(t['amount'], t['currency'], cur), cur)}{period}.{note}")
    if op in ("pe_categorii", "pe_comercianti"):
        parts = "; ".join(f"{b['label']}: {fmt(b['value'], cur)}" for b in r["breakdown"][:10])
        return f"Total {fmt(r['total'], cur)}{what}{period}. Defalcare – {parts}.{note}"
    if op == "lista":
        return f"Am găsit {n} {plural}{what}{period}, total {fmt(r['total'], cur)}. Le vezi evidențiate mai jos.{note}"
    return f"{verb.capitalize()} {fmt(r['total'], cur)}{what}{period} ({n} {plural}).{note}"
