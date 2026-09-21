"""Tests for the deterministic, data-driven recommendations engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_pipeline import run_pipeline  # noqa: E402
from recommendations import MARKET_CONTEXT, generate_recommendations  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def test_market_context_always_present():
    raw = (SAMPLE_DIR / "vanzari.csv").read_bytes()
    result = run_pipeline(raw)
    recs = generate_recommendations(result)
    assert recs["market_context"] == MARKET_CONTEXT
    assert all("source" in item for item in recs["market_context"])


def test_detects_client_concentration_on_vanzari_2026():
    raw = (SAMPLE_DIR / "vanzari_2026.csv").read_bytes()
    result = run_pipeline(raw)
    recs = generate_recommendations(result)
    titles = [r["title"] for r in recs["data_driven"]]
    assert any("Farmacia Vita" in t for t in titles)


def test_detects_currency_concentration_on_vanzari_2026():
    raw = (SAMPLE_DIR / "vanzari_2026.csv").read_bytes()
    result = run_pipeline(raw)
    recs = generate_recommendations(result)
    titles = [r["title"] for r in recs["data_driven"]]
    assert any("RON" in t for t in titles)


def test_detects_monthly_low_on_vanzari_2026():
    raw = (SAMPLE_DIR / "vanzari_2026.csv").read_bytes()
    result = run_pipeline(raw)
    recs = generate_recommendations(result)
    titles = [r["title"] for r in recs["data_driven"]]
    assert any("2026-05" in t for t in titles)


def test_detects_anomaly_count_on_vanzari_2026():
    raw = (SAMPLE_DIR / "vanzari_2026.csv").read_bytes()
    result = run_pipeline(raw)
    recs = generate_recommendations(result)
    anomaly_recs = [r for r in recs["data_driven"] if "valori neobișnuite" in r["title"]]
    assert len(anomaly_recs) == 1
    assert str(len(result.anomalies)) in anomaly_recs[0]["title"]


def test_no_crash_on_csv_without_date_or_currency_columns():
    raw = b"produs,cantitate\nA,5\nB,3\nC,1\n"
    result = run_pipeline(raw)
    recs = generate_recommendations(result)
    assert isinstance(recs["data_driven"], list)


def test_recommendations_are_json_serializable():
    import json

    raw = (SAMPLE_DIR / "vanzari_2026.csv").read_bytes()
    result = run_pipeline(raw)
    recs = generate_recommendations(result)
    json.dumps(recs)
