"""Analizor de cheltuieli – server FastAPI.

Pornire:  uvicorn backend.main:app --reload   (din folderul analizor-cheltuieli)
"""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, local_query
from .categorize import categorize, remember
from .parsers import ParseError, detect_currency, parse_amount, parse_card_csv, parse_date, parse_statement_pdf
from .store import RATES, SOURCE_LABEL, Store

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Analizor de cheltuieli")
store = Store()

IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
MAX_FILE = 15 * 1024 * 1024

# Cache pentru întrebări: aceeași întrebare pe aceleași luni nu mai costă un apel.
_q_cache: OrderedDict[str, dict] = OrderedDict()


# ------------------------------------------------------------------ upload
@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    reports = []
    for f in files:
        raw = await f.read()
        reports.append(_ingest(f.filename or "fisier", raw))
    return {"reports": reports, "transactions": store.txs}


def _ingest(name: str, raw: bytes) -> dict:
    rep = {"file": name, "added": 0, "warnings": [], "error": None, "source": None, "categorii": None}
    if not raw:
        rep["error"] = "Fișier gol."
        return rep
    if len(raw) > MAX_FILE:
        rep["error"] = "Fișier prea mare (max 15 MB)."
        return rep
    h = store.file_hash(raw)
    if (prev := store.seen_file(h)):
        rep["error"] = f"Fișierul a fost deja încărcat (ca „{prev}”) – l-am ignorat ca să nu dublez sumele."
        return rep

    ext = Path(name).suffix.lower()
    try:
        if ext in (".csv", ".txt"):
            rep["source"] = "card_csv"
            txs, warns = parse_card_csv(raw)
        elif ext == ".pdf":
            rep["source"] = "extras_pdf"
            try:
                txs, warns = parse_statement_pdf(raw)
            except ParseError:
                txs, warns = [], []
            if not txs:  # PDF scanat / format necunoscut -> abia atunci plătim AI-ul
                txs, warns = _ai_document(raw, "application/pdf", "extras_pdf"), ["PDF citit cu AI (textul nu a putut fi parsat local)."]
        elif ext in IMAGE_TYPES:
            rep["source"] = "bon"
            txs, warns = _ai_document(raw, IMAGE_TYPES[ext], "bon"), []
        else:
            raise ParseError("Format necunoscut. Acceptat: .csv, .pdf, .jpg, .png, .webp.")
    except (ParseError, ai.AIUnavailable) as e:
        rep["error"] = str(e)
        if isinstance(e, ai.AIUnavailable) and ext in IMAGE_TYPES:
            rep["error"] += " Poți adăuga bonul manual din formularul „Adaugă manual”."
        return rep

    if not txs:
        rep["error"] = "Nu am găsit nicio tranzacție în fișier."
        return rep
    rep["categorii"] = categorize(txs)
    store.add(txs, name, h)
    rep["added"] = len(txs)
    rep["warnings"] = warns
    return rep


def _ai_document(raw: bytes, media_type: str, source: str) -> list[dict]:
    items = ai.extract_document(raw, media_type)
    out = []
    for it in items:
        d = parse_date(it.get("data", ""))
        amount = parse_amount(str(it.get("suma", "")))
        if d is None or not amount:
            continue
        out.append({
            "date": d.isoformat(),
            "description": (it.get("descriere") or "Bon").strip(),
            "amount": round(abs(amount), 2),
            "currency": it.get("moneda") if it.get("moneda") in RATES else "RON",
            "direction": it.get("directie") if it.get("directie") in ("debit", "credit") else "debit",
            "source": source,
            "category": it.get("categorie") if it.get("categorie") in ai.CATEGORII else None,
            "category_by": "AI (din imagine)" if source == "bon" else "AI",
        })
    return out


# ------------------------------------------------------------------ tranzacții
@app.get("/api/transactions")
def list_transactions():
    return {"transactions": store.txs}


class ManualTx(BaseModel):
    date: str
    description: str
    amount: str
    currency: str = "RON"
    direction: str = "debit"
    category: str | None = None
    source: str = "bon"


@app.post("/api/transactions")
def add_manual(tx: ManualTx):
    d, amount = parse_date(tx.date), parse_amount(tx.amount)
    if d is None:
        raise HTTPException(400, "Dată invalidă.")
    if not amount:
        raise HTTPException(400, "Sumă invalidă.")
    item = {
        "date": d.isoformat(), "description": tx.description.strip() or "Bon numerar",
        "amount": round(abs(amount), 2), "currency": detect_currency(tx.currency),
        "direction": "credit" if tx.direction == "credit" else "debit",
        "source": tx.source if tx.source in SOURCE_LABEL else "bon",
    }
    if tx.category in ai.CATEGORII:
        item["category"], item["category_by"] = tx.category, "manual"
    categorize([item])
    store.add([item], "adăugat manual", None)
    return item


class Patch(BaseModel):
    category: str


@app.patch("/api/transactions/{tx_id}")
def patch(tx_id: str, body: Patch):
    if body.category not in ai.CATEGORII:
        raise HTTPException(400, "Categorie invalidă.")
    tx = store.update(tx_id, category=body.category, category_by="manual")
    if not tx:
        raise HTTPException(404, "Tranzacția nu există.")
    if tx["direction"] == "debit":
        remember(tx["description"], body.category)
    _q_cache.clear()
    return tx


@app.delete("/api/transactions/{tx_id}")
def delete(tx_id: str):
    if not store.delete(tx_id):
        raise HTTPException(404, "Tranzacția nu există.")
    _q_cache.clear()
    return {"ok": True}


@app.delete("/api/transactions")
def reset():
    store.reset()
    _q_cache.clear()
    return {"ok": True}


# ------------------------------------------------------------------ întrebări
class Ask(BaseModel):
    question: str
    display_currency: str = "RON"


@app.post("/api/ask")
def ask(body: Ask):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Scrie o întrebare.")
    if not store.txs:
        return {"answer": "Încarcă mai întâi un fișier cu tranzacții.", "query": None, "ids": []}

    months = store.months()
    key = hashlib.sha1(f"{question.lower()}|{','.join(months)}".encode()).hexdigest()
    started = time.time()
    mode, warning = "AI", None
    if key in _q_cache:
        q, mode = _q_cache[key], "cache"
    else:
        try:
            q = ai.parse_question(question, {"luni": months})
        except ai.AIUnavailable as e:
            q, mode, warning = local_query.parse(question, months), "local", str(e)
        _q_cache[key] = q
        if len(_q_cache) > 200:
            _q_cache.popitem(last=False)

    if q.get("in_afara_domeniului"):
        return {"answer": "Pot răspunde doar la întrebări despre tranzacțiile încărcate.", "query": q, "ids": [], "mode": mode}

    cur = body.display_currency if body.display_currency in RATES else "RON"
    res = store.run_query(q, cur)
    return {**res, "query": q, "mode": mode, "warning": warning, "ms": int((time.time() - started) * 1000)}


# ------------------------------------------------------------------ status & UI
@app.get("/api/status")
def status():
    return {
        "ai_enabled": ai.enabled(), "model": ai.MODEL, "usage": ai.usage,
        "rates": RATES, "categories": ai.CATEGORII, "sources": SOURCE_LABEL,
    }


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")
