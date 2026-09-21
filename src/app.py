"""
CSV Sales Dashboard API

Upload any sales CSV — clean or messy — and get back a cleaned table,
aggregates, and anomalies within seconds. The model never computes a
number: pandas does the arithmetic, the model (in /ask) only explains it.
"""

import csv
import hashlib
import io
import os
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
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

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB — enough for any realistic sales export
MAX_CACHED_FILES = 50  # bound memory use on a long-running server

# In-memory cache keyed by file content hash — re-uploading the same CSV is instant.
# Bounded LRU: the oldest entry is evicted once the cap is reached.
_cache: "OrderedDict[str, PipelineResult]" = OrderedDict()


def _cache_get(file_hash: str) -> PipelineResult | None:
    result = _cache.get(file_hash)
    if result is not None:
        _cache.move_to_end(file_hash)
    return result


def _cache_set(file_hash: str, result: PipelineResult) -> None:
    _cache[file_hash] = result
    _cache.move_to_end(file_hash)
    while len(_cache) > MAX_CACHED_FILES:
        _cache.popitem(last=False)


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Accept a CSV, clean it, and return the hash used to fetch its data/ask questions."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Fișierul e gol")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Fișierul e prea mare (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )

    file_hash = hashlib.sha1(raw).hexdigest()
    result = _cache_get(file_hash)
    if result is None:
        try:
            result = run_pipeline(raw)
        except Exception as exc:  # noqa: BLE001 - surface any parsing failure to the caller
            raise HTTPException(status_code=400, detail=f"Nu am putut citi CSV-ul: {exc}") from exc
        _cache_set(file_hash, result)

    return {"hash": file_hash, "recommendations": generate_recommendations(result), **result.as_dict()}


@app.get("/data/{file_hash}")
def get_data(file_hash: str):
    """Return the cleaned table + aggregates for a previously uploaded CSV."""
    result = _cache_get(file_hash)
    if result is None:
        raise HTTPException(status_code=404, detail="Fișier necunoscut — reîncarcă CSV-ul")
    return {
        "hash": file_hash,
        "table": result.table,
        "recommendations": generate_recommendations(result),
        **result.as_dict(),
    }


@app.get("/data/{file_hash}/export.csv")
def export_csv(file_hash: str):
    """Download the cleaned table as a CSV file."""
    result = _cache_get(file_hash)
    if result is None:
        raise HTTPException(status_code=404, detail="Fișier necunoscut — reîncarcă CSV-ul")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=result.columns)
    writer.writeheader()
    writer.writerows(result.table)

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="curatat-{file_hash[:8]}.csv"'},
    )


class AskRequest(BaseModel):
    hash: str
    question: str


@app.post("/ask")
def ask(payload: AskRequest):
    """Answer a Romanian question grounded in the aggregates already computed for this file."""
    result = _cache_get(payload.hash)
    if result is None:
        raise HTTPException(status_code=404, detail="Fișier necunoscut — reîncarcă CSV-ul")
    return {"answer": answer_question(payload.question, result)}
