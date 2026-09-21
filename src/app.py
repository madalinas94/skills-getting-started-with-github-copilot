"""
CSV Sales Dashboard API

Upload any sales CSV — clean or messy — and get back a cleaned table,
aggregates, and anomalies within seconds. The model never computes a
number: pandas does the arithmetic, the model (in /ask) only explains it.
"""

import hashlib
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from data_pipeline import PipelineResult, run_pipeline
from qa import answer_question
from recommendations import generate_recommendations

app = FastAPI(
    title="CSV Sales Dashboard",
    description="Urci un CSV de vânzări și primești tabel curățat, agregate, grafice și răspunsuri în română.",
)

current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")

# In-memory cache keyed by file content hash — re-uploading the same CSV is instant.
_cache: dict[str, PipelineResult] = {}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Accept a CSV, clean it, and return the hash used to fetch its data/ask questions."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Fișierul e gol")

    file_hash = hashlib.sha1(raw).hexdigest()
    if file_hash not in _cache:
        try:
            _cache[file_hash] = run_pipeline(raw)
        except Exception as exc:  # noqa: BLE001 - surface any parsing failure to the caller
            raise HTTPException(status_code=400, detail=f"Nu am putut citi CSV-ul: {exc}") from exc

    result = _cache[file_hash]
    return {"hash": file_hash, "recommendations": generate_recommendations(result), **result.as_dict()}


@app.get("/data/{file_hash}")
def get_data(file_hash: str):
    """Return the cleaned table + aggregates for a previously uploaded CSV."""
    result = _cache.get(file_hash)
    if result is None:
        raise HTTPException(status_code=404, detail="Fișier necunoscut — reîncarcă CSV-ul")
    return {
        "hash": file_hash,
        "table": result.table,
        "recommendations": generate_recommendations(result),
        **result.as_dict(),
    }


class AskRequest(BaseModel):
    hash: str
    question: str


@app.post("/ask")
def ask(payload: AskRequest):
    """Answer a Romanian question grounded in the aggregates already computed for this file."""
    result = _cache.get(payload.hash)
    if result is None:
        raise HTTPException(status_code=404, detail="Fișier necunoscut — reîncarcă CSV-ul")
    return {"answer": answer_question(payload.question, result)}
