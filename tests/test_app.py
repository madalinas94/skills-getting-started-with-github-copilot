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


def test_upload_oversized_file_is_rejected():
    import app as app_module

    too_big = b"a" * (app_module.MAX_UPLOAD_BYTES + 1)
    res = client.post("/upload", files={"file": ("huge.csv", too_big, "text/csv")})
    assert res.status_code == 400
    assert "mare" in res.json()["detail"]


def test_upload_includes_recommendations():
    body = _upload("vanzari_2026.csv").json()
    assert "recommendations" in body
    assert "market_context" in body["recommendations"]


def test_export_csv_downloads_cleaned_table():
    upload = _upload("vanzari_2026.csv").json()
    res = client.get(f"/data/{upload['hash']}/export.csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    lines = res.text.strip().splitlines()
    assert len(lines) == upload["row_count"] + 1  # header + rows


def test_export_csv_unknown_hash_is_404():
    res = client.get("/data/does-not-exist/export.csv")
    assert res.status_code == 404


def test_cache_evicts_oldest_entry_past_cap():
    import app as app_module

    original_cap = app_module.MAX_CACHED_FILES
    app_module.MAX_CACHED_FILES = 1
    try:
        # Fresh, never-before-uploaded content so this test doesn't hit the
        # cache another test already populated.
        first = client.post(
            "/upload", files={"file": ("evict-a.csv", b"produs,cantitate\nA,1\n", "text/csv")}
        ).json()
        client.post("/upload", files={"file": ("evict-b.csv", b"produs,cantitate\nB,2\n", "text/csv")})
        res = client.get(f"/data/{first['hash']}")
        assert res.status_code == 404
    finally:
        app_module.MAX_CACHED_FILES = original_cap
