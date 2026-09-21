"""Smoke tests for the FastAPI endpoints (upload, data, ask)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"

client = TestClient(app)


def _upload(filename: str):
    with open(SAMPLE_DIR / filename, "rb") as f:
        return client.post("/upload", files={"file": (filename, f, "text/csv")})


def test_upload_returns_cleaned_summary():
    res = _upload("vanzari_2026.csv")
    assert res.status_code == 200
    body = res.json()
    assert body["row_count"] > 0
    assert "hash" in body
    assert body["report"]["total_rows_removed"] >= 2


def test_upload_empty_file_is_rejected():
    res = client.post("/upload", files={"file": ("empty.csv", b"", "text/csv")})
    assert res.status_code == 400


def test_data_endpoint_returns_full_table():
    upload = _upload("vanzari_2026.csv").json()
    res = client.get(f"/data/{upload['hash']}")
    assert res.status_code == 200
    assert len(res.json()["table"]) == upload["row_count"]


def test_data_endpoint_unknown_hash_is_404():
    res = client.get("/data/does-not-exist")
    assert res.status_code == 404


def test_ask_answers_without_computing_numbers_itself():
    upload = _upload("vanzari_2026.csv").json()
    res = client.post("/ask", json={"hash": upload["hash"], "question": "Cat e totalul vanzarilor?"})
    assert res.status_code == 200
    answer = res.json()["answer"]
    total = upload["aggregates"]["stats"][upload["aggregates"]["value_column"]]["sum"]
    assert f"{total:,.2f}" in answer


def test_ask_unknown_hash_is_404():
    res = client.post("/ask", json={"hash": "nope", "question": "?"})
    assert res.status_code == 404


def test_reuploading_same_file_hits_cache():
    first = _upload("vanzari.csv").json()
    second = _upload("vanzari.csv").json()
    assert first["hash"] == second["hash"]
