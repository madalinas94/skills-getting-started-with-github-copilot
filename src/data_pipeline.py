"""
CSV Sales Dashboard — data pipeline.

Parses, cleans, and aggregates an arbitrary sales CSV so the model never has
to compute a single number: every figure in this module comes from pandas,
not from an LLM.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_DELIMITER_CANDIDATES = (",", ";", "\t", "|")


def _decode(raw: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _detect_delimiter(text: str) -> str:
    sample_lines = [line for line in text.splitlines() if line.strip()][:20]
    counts = {d: sum(line.count(d) for line in sample_lines) for d in _DELIMITER_CANDIDATES}
    return max(counts, key=counts.get)


def _count_fields(line: str, delimiter: str) -> int:
    """Field count respecting quoted values, so a quoted 'Lei 4.500,00' isn't split on its comma."""
    try:
        row = next(csv.reader([line], delimiter=delimiter))
    except StopIteration:
        return 0
    return len(row)


def _find_header_row(lines: list[str], delimiter: str) -> int:
    """Skip metadata lines (report titles, generation timestamps) before the real header."""
    field_counts = [_count_fields(line, delimiter) for line in lines]
    if not field_counts:
        return 0
    target = max(field_counts)
    for i, count in enumerate(field_counts):
        if count == target:
            return i
    return 0


def read_csv_tolerant(raw: bytes) -> pd.DataFrame:
    """Read any CSV: unknown delimiter, unknown encoding, metadata lines before the header."""
    text = _decode(raw)
    lines = text.splitlines()
    delimiter = _detect_delimiter(text)
    header_row = _find_header_row(lines, delimiter)

    df = pd.read_csv(
        io.StringIO(text),
        sep=delimiter,
        skiprows=header_row,
        engine="python",
        dtype=str,
        keep_default_na=False,
        on_bad_lines="skip",
    )
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    return df


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

_TOTAL_ROW_PATTERN = re.compile(r"(?i)^(sub)?total(\s+\w+)*$")
_CURRENCY_NOISE = re.compile(r"(?i)\s*(lei|ron|eur|usd|€|\$)\s*")
_DATE_PATTERNS = (
    re.compile(r"^\d{1,2}\.\d{1,2}\.\d{2,4}$"),
    re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$"),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$"),
)
_ISO_DATE_PATTERN = _DATE_PATTERNS[1]

_DATE_KEYWORDS = ("data", "date", "datum")
_NUMERIC_KEYWORDS = ("pret", "preț", "cantitate", "suma", "sumă", "valoare", "total", "qty", "price")
_CATEGORY_KEYWORDS = ("client", "produs", "regiune", "vanzator", "vânzător", "status", "valuta", "nume")
_NAME_LIKE_KEYWORDS = ("client", "vanzator", "vânzător", "nume", "name", "customer", "angajat")


def _is_blank_row(row: pd.Series) -> bool:
    return all(str(v).strip() == "" for v in row)


def _is_total_row(row: pd.Series) -> bool:
    for v in row:
        s = str(v).strip()
        if s and _TOTAL_ROW_PATTERN.match(s):
            return True
    return False


def parse_number(value: Any) -> float | None:
    """Parse a number written in Romanian or plain notation: '1.841,86 lei' -> 1841.86."""
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    v = _CURRENCY_NOISE.sub("", v)
    if re.search(r"[A-Za-z]", v):
        # leftover letters (e.g. an order id like "CMD-100043") -> not a number
        return None
    v = re.sub(r"[^\d,.\-]", "", v)
    if not v:
        return None
    if "," in v and "." in v:
        v = v.replace(".", "").replace(",", ".")
    elif "," in v:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def _looks_like_date(value: str) -> bool:
    v = value.strip()
    return any(p.match(v) for p in _DATE_PATTERNS)


def _infer_dayfirst(series: pd.Series) -> bool:
    """ISO dates (2025-01-05) are unambiguous year-first; D.M.Y / D/M/Y need dayfirst=True."""
    sample = series.dropna().astype(str)
    sample = sample[sample.str.strip() != ""].head(20)
    if sample.empty:
        return True
    iso_like = sample.apply(lambda v: bool(_ISO_DATE_PATTERN.match(v.strip()))).mean()
    return iso_like < 0.5


def _canonicalize_case(series: pd.Series) -> tuple[pd.Series, dict[str, list[str]]]:
    """First-seen casing wins for values equal except for letter case."""
    seen: dict[str, str] = {}
    variants: dict[str, set[str]] = {}
    result = []
    for val in series:
        s = str(val).strip()
        key = s.lower()
        canon = seen.setdefault(key, s)
        if s != canon:
            variants.setdefault(canon, set()).add(s)
        result.append(canon)
    merged = {canon: sorted(vs) for canon, vs in variants.items()}
    return pd.Series(result, index=series.index), merged


def _fuzzy_canonicalize(values: list[str], threshold: int = 90) -> dict[str, str]:
    """Cluster near-duplicate free-text values (e.g. name variants) to one canonical form."""
    canonical: list[str] = []
    mapping: dict[str, str] = {}
    for v in values:
        key = v.strip()
        if not key:
            continue
        match = None
        for c in canonical:
            if fuzz.token_sort_ratio(key.lower(), c.lower()) >= threshold:
                match = c
                break
        if match is None:
            canonical.append(key)
            mapping[key] = key
        else:
            mapping[key] = match
    return mapping


def detect_column_roles(df: pd.DataFrame) -> dict[str, str]:
    """Classify each column as 'date', 'numeric', or 'categorical' — by name, then by content."""
    roles: dict[str, str] = {}
    for col in df.columns:
        name = col.strip().lower()
        if any(k in name for k in _DATE_KEYWORDS):
            roles[col] = "date"
            continue
        if any(k in name for k in _NUMERIC_KEYWORDS):
            roles[col] = "numeric"
            continue
        if any(k in name for k in _CATEGORY_KEYWORDS):
            roles[col] = "categorical"
            continue

        sample = df[col].dropna().astype(str)
        sample = sample[sample.str.strip() != ""].head(20)
        if sample.empty:
            roles[col] = "categorical"
            continue
        date_like = sample.apply(_looks_like_date).mean()
        numeric_like = sample.apply(lambda v: parse_number(v) is not None).mean()
        if date_like > 0.6:
            roles[col] = "date"
        elif numeric_like > 0.6:
            roles[col] = "numeric"
        else:
            roles[col] = "categorical"
    return roles


@dataclass
class CleaningReport:
    rows_in: int
    rows_out: int
    blank_rows_removed: int
    total_rows_removed: int
    duplicate_rows_removed: int
    name_variants_merged: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "blank_rows_removed": self.blank_rows_removed,
            "total_rows_removed": self.total_rows_removed,
            "duplicate_rows_removed": self.duplicate_rows_removed,
            "name_variants_merged": self.name_variants_merged,
        }


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], CleaningReport]:
    rows_in = len(df)
    df = df.copy()

    blank_mask = df.apply(_is_blank_row, axis=1)
    blank_removed = int(blank_mask.sum())
    df = df[~blank_mask]

    total_mask = df.apply(_is_total_row, axis=1)
    total_removed = int(total_mask.sum())
    df = df[~total_mask]

    roles = detect_column_roles(df)

    for col, role in roles.items():
        if role == "numeric":
            df[col] = df[col].apply(parse_number)
        elif role == "date":
            df[col] = pd.to_datetime(df[col], dayfirst=_infer_dayfirst(df[col]), errors="coerce")

    name_variants: dict[str, dict[str, list[str]]] = {}
    for col, role in roles.items():
        if role != "categorical":
            continue
        df[col], case_merged = _canonicalize_case(df[col])
        col_variants: dict[str, set[str]] = {k: set(v) for k, v in case_merged.items()}

        is_name_like = any(k in col.strip().lower() for k in _NAME_LIKE_KEYWORDS)
        if is_name_like:
            mapping = _fuzzy_canonicalize(sorted(df[col].dropna().unique().tolist()))
            for original, canon in mapping.items():
                if original != canon:
                    col_variants.setdefault(canon, set()).add(original)
            df[col] = df[col].map(lambda v, m=mapping: m.get(v, v))

        if col_variants:
            name_variants[col] = {canon: sorted(vs) for canon, vs in col_variants.items()}

    before_dedup = len(df)
    df = df.drop_duplicates()
    duplicate_removed = before_dedup - len(df)

    df = df.reset_index(drop=True)
    report = CleaningReport(
        rows_in=rows_in,
        rows_out=len(df),
        blank_rows_removed=blank_removed,
        total_rows_removed=total_removed,
        duplicate_rows_removed=duplicate_removed,
        name_variants_merged=name_variants,
    )
    return df, roles, report


# ---------------------------------------------------------------------------
# Derived columns + aggregation
# ---------------------------------------------------------------------------

_QUANTITY_KEYWORDS = ("cantitate", "qty", "buc")
_PRICE_KEYWORDS = ("pret", "preț", "price")


def add_derived_value_column(
    df: pd.DataFrame, roles: dict[str, str]
) -> tuple[pd.DataFrame, dict[str, str], str | None]:
    """If quantity + unit price columns exist, add Valoare = cantitate * pret (code, not the model)."""
    qty_col = next(
        (c for c, r in roles.items() if r == "numeric" and any(k in c.lower() for k in _QUANTITY_KEYWORDS)),
        None,
    )
    price_col = next(
        (c for c, r in roles.items() if r == "numeric" and any(k in c.lower() for k in _PRICE_KEYWORDS)),
        None,
    )
    if qty_col and price_col and qty_col != price_col:
        df = df.copy()
        df["Valoare"] = df[qty_col].fillna(0) * df[price_col].fillna(0)
        roles = {**roles, "Valoare": "numeric"}
        return df, roles, "Valoare"
    return df, roles, None


def compute_aggregates(df: pd.DataFrame, roles: dict[str, str]) -> dict[str, Any]:
    numeric_cols = [c for c, r in roles.items() if r == "numeric"]
    categorical_cols = [c for c, r in roles.items() if r == "categorical"]

    stats: dict[str, Any] = {}
    for col in numeric_cols:
        s = df[col].dropna()
        if s.empty:
            continue
        stats[col] = {
            "sum": round(float(s.sum()), 2),
            "mean": round(float(s.mean()), 2),
            "min": round(float(s.min()), 2),
            "max": round(float(s.max()), 2),
            "count": int(s.count()),
        }

    value_col = "Valoare" if "Valoare" in numeric_cols else (numeric_cols[0] if numeric_cols else None)

    # Skip identifier-like columns (near-unique per row, e.g. an order number) — grouping by
    # them isn't a meaningful breakdown, just the raw rows again.
    breakdown_cols = [
        col for col in categorical_cols if len(df) == 0 or df[col].nunique(dropna=True) / len(df) <= 0.6
    ]

    top_by: dict[str, list[dict[str, Any]]] = {}
    if value_col:
        for col in breakdown_cols:
            grouped = df.groupby(col)[value_col].sum().sort_values(ascending=False)
            top_by[col] = [{"key": str(k), "value": round(float(v), 2)} for k, v in grouped.head(10).items()]

    return {"stats": stats, "value_column": value_col, "top_by": top_by}


def detect_anomalies(df: pd.DataFrame, roles: dict[str, str], value_col: str | None) -> list[dict[str, Any]]:
    """Flag outliers via IQR — the dashboard finds what's odd in the data on its own."""
    anomalies: list[dict[str, Any]] = []
    cols = [value_col] if value_col else [c for c, r in roles.items() if r == "numeric"]
    for col in cols:
        if not col or col not in df.columns:
            continue
        s = df[col].dropna()
        if len(s) < 4:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = df[(df[col] < lower) | (df[col] > upper)]
        for idx, row in outliers.iterrows():
            anomalies.append(
                {
                    "row": int(idx),
                    "column": col,
                    "value": round(float(row[col]), 2),
                    "bounds": [round(float(lower), 2), round(float(upper), 2)],
                }
            )
    return anomalies


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    table: list[dict[str, Any]]
    columns: list[str]
    roles: dict[str, str]
    aggregates: dict[str, Any]
    anomalies: list[dict[str, Any]]
    report: CleaningReport

    def as_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "roles": self.roles,
            "aggregates": self.aggregates,
            "anomalies": self.anomalies,
            "report": self.report.as_dict(),
            "row_count": len(self.table),
        }


def run_pipeline(raw_csv: bytes) -> PipelineResult:
    df = read_csv_tolerant(raw_csv)
    cleaned, roles, report = clean_dataframe(df)
    cleaned, roles, value_col = add_derived_value_column(cleaned, roles)
    aggregates = compute_aggregates(cleaned, roles)
    anomalies = detect_anomalies(cleaned, roles, value_col)

    table_df = cleaned.copy()
    for col, role in roles.items():
        if role == "date":
            table_df[col] = table_df[col].dt.strftime("%Y-%m-%d")
    # NaN/NaT -> null: to_json (not .where, which recasts None back to NaN on numeric dtypes).
    table = json.loads(table_df.to_json(orient="records"))

    return PipelineResult(
        table=table,
        columns=list(cleaned.columns),
        roles=roles,
        aggregates=aggregates,
        anomalies=anomalies,
        report=report,
    )
