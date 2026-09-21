"""Tests for the CSV cleaning pipeline against messy, real-world-shaped input."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_pipeline import (  # noqa: E402
    clean_dataframe,
    parse_number,
    read_csv_tolerant,
    run_pipeline,
)

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def test_parse_number_romanian_format():
    assert parse_number("1.841,86") == 1841.86
    assert parse_number("4.500,00 lei") == 4500.0
    assert parse_number("250 lei") == 250.0
    assert parse_number("120") == 120.0
    assert parse_number("") is None
    assert parse_number(None) is None


def test_parse_number_rejects_ids_with_letters():
    # An order id like "CMD-100043" must never be treated as a number.
    assert parse_number("CMD-100043") is None


def test_read_csv_tolerant_handles_quoted_delimiter_in_value():
    raw = (
        "produs,cantitate,pret\n"
        'Tastatura,5,"250 lei"\n'
        'Laptop,1,"4.500,00 lei"\n'
    ).encode("utf-8")
    df = read_csv_tolerant(raw)
    assert list(df.columns) == ["produs", "cantitate", "pret"]
    assert len(df) == 2


def test_read_csv_tolerant_skips_metadata_lines_before_header():
    raw = (
        "EXPORT VANZARI - sistem intern\n"
        "Perioada: 01.01.2026 - 31.08.2026\n"
        "\n"
        "Nr comanda;Client;Suma\n"
        "CMD-1;Acme;100,00\n"
        "CMD-2;Beta;200,00\n"
    ).encode("utf-8")
    df = read_csv_tolerant(raw)
    assert list(df.columns) == ["Nr comanda", "Client", "Suma"]
    assert len(df) == 2


def test_clean_dataframe_drops_blank_and_total_rows():
    raw = (
        "produs,cantitate,pret\n"
        "A,1,10\n"
        ",,\n"
        "TOTAL,,10\n"
        "B,2,20\n"
    ).encode("utf-8")
    df = read_csv_tolerant(raw)
    cleaned, roles, report = clean_dataframe(df)
    assert report.blank_rows_removed == 1
    assert report.total_rows_removed == 1
    assert len(cleaned) == 2


def test_clean_dataframe_unifies_name_case_variants():
    raw = (
        "client,suma\n"
        "Delta Foods SA,100\n"
        "DELTA FOODS SA,200\n"
        "delta foods sa,300\n"
    ).encode("utf-8")
    df = read_csv_tolerant(raw)
    cleaned, roles, report = clean_dataframe(df)
    assert cleaned["client"].nunique() == 1
    assert "client" in report.name_variants_merged


def test_clean_dataframe_removes_case_only_duplicate_rows():
    raw = ("produs,status\n" "A,Livrata\n" "A,LIVRATA\n").encode("utf-8")
    df = read_csv_tolerant(raw)
    cleaned, roles, report = clean_dataframe(df)
    assert len(cleaned) == 1
    assert report.duplicate_rows_removed == 1


def test_fuzzy_dedup_does_not_merge_similar_order_ids():
    # rapidfuzz would rate "CMD-100002" vs "CMD-100003" as near-identical text,
    # but an id column must never be fuzzy-merged.
    raw = (
        "nr comanda,client,suma\n"
        "CMD-100002,Acme,100\n"
        "CMD-100003,Acme,200\n"
    ).encode("utf-8")
    df = read_csv_tolerant(raw)
    cleaned, roles, report = clean_dataframe(df)
    assert set(cleaned["nr comanda"]) == {"CMD-100002", "CMD-100003"}


def test_iso_dates_are_not_misparsed_as_day_first():
    raw = ("produs,data\n" "A,2025-01-13\n" "B,2025-01-05\n").encode("utf-8")
    df = read_csv_tolerant(raw)
    cleaned, roles, _ = clean_dataframe(df)
    assert roles["data"] == "date"
    parsed = cleaned["data"].dt.strftime("%Y-%m-%d").tolist()
    assert "2025-01-13" in parsed  # day=13 would be an invalid month if swapped
    assert "2025-01-05" in parsed  # must not become 2025-05-01


def test_run_pipeline_on_vanzari_sample():
    raw = (SAMPLE_DIR / "vanzari.csv").read_bytes()
    result = run_pipeline(raw)
    assert result.report.rows_out > 0
    assert result.report.total_rows_removed == 2
    assert result.aggregates["value_column"] == "Valoare"


def test_run_pipeline_on_vanzari_2026_sample():
    raw = (SAMPLE_DIR / "vanzari_2026.csv").read_bytes()
    result = run_pipeline(raw)
    report = result.report
    assert report.total_rows_removed >= 2  # the TOTAL PARTIAL rows
    assert report.duplicate_rows_removed >= 1  # the exact duplicate CMD-100033 row
    assert "Client" in report.name_variants_merged  # Delta Foods SA casing variants
    assert "Nr comanda" not in result.aggregates["top_by"]  # identifier column excluded


def test_run_pipeline_output_is_json_safe():
    import json

    for fname in ("vanzari.csv", "vanzari_2026.csv"):
        raw = (SAMPLE_DIR / fname).read_bytes()
        result = run_pipeline(raw)
        json.dumps(result.as_dict())
        json.dumps(result.table)
