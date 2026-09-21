"""
Romanian Q&A over pre-computed aggregates.

The model (when available) only explains numbers this module already
computed — it is never given the raw CSV and never asked to compute
anything itself.
"""

from __future__ import annotations

import os
from typing import Any

from data_pipeline import PipelineResult

_SYSTEM_PROMPT = (
    "Ești un asistent de analiză vânzări. Ai la dispoziție DOAR un rezumat "
    "numeric precalculat al unui CSV (nu CSV-ul brut). Răspunde în română, "
    "scurt și concret, folosind exclusiv cifrele din rezumat. Nu inventa și "
    "nu recalcula cifre — dacă informația nu e în rezumat, spune că nu poți "
    "răspunde din datele disponibile."
)


def build_summary(result: PipelineResult) -> dict[str, Any]:
    """The only thing the model ever sees — numbers, not rows."""
    return {
        "coloane": result.columns,
        "roluri_coloane": result.roles,
        "curatare": result.report.as_dict(),
        "agregate": result.aggregates,
        "anomalii": result.anomalies,
        "numar_randuri": len(result.table),
    }


def _fallback_answer(question: str, summary: dict[str, Any]) -> str:
    """Deterministic Romanian answer used when no LLM key is configured."""
    q = question.lower()
    aggregates = summary["agregate"]
    value_col = aggregates.get("value_column")
    stats = aggregates.get("stats", {})
    top_by = aggregates.get("top_by", {})

    if any(k in q for k in ("cine", "client", "cel mai bun", "top")) and top_by:
        col = next((c for c in top_by if c.lower() in q), None) or next(iter(top_by))
        leader = top_by[col][0] if top_by[col] else None
        if leader:
            return f"Primul loc la „{col}” este „{leader['key']}” cu {leader['value']:,.2f} pe coloana {value_col}."

    if any(k in q for k in ("cat", "cât", "total", "suma", "sumă")) and value_col and value_col in stats:
        s = stats[value_col]
        return (
            f"Totalul pe „{value_col}” este {s['sum']:,.2f} (medie {s['mean']:,.2f}, "
            f"pe {s['count']} rânduri, min {s['min']:,.2f}, max {s['max']:,.2f})."
        )

    if any(k in q for k in ("anomalie", "ciudat", "outlier", "neobisnuit", "neobișnuit")):
        anomalies = summary.get("anomalii", [])
        if anomalies:
            a = anomalies[0]
            return f"Am găsit {len(anomalies)} valori neobișnuite — cea mai mare pe „{a['column']}” este {a['value']:,.2f}."
        return "Nu am găsit valori neobișnuite în date."

    if any(k in q for k in ("curat", "rand", "rând", "murdar")):
        r = summary["curatare"]
        return (
            f"Din {r['rows_in']} rânduri am păstrat {r['rows_out']}: "
            f"{r['blank_rows_removed']} goale, {r['total_rows_removed']} de total, "
            f"{r['duplicate_rows_removed']} duplicate eliminate."
        )

    if value_col and value_col in stats:
        s = stats[value_col]
        return (
            f"Nu sunt sigur exact ce întrebi, dar iată un rezumat: {summary['numar_randuri']} rânduri, "
            f"total „{value_col}” = {s['sum']:,.2f}."
        )
    return "Nu am suficiente date numerice ca să răspund la asta."


def _anthropic_answer(question: str, summary: dict[str, Any]) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=400,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Rezumat date:\n{summary}\n\nÎntrebare: {question}"}],
    )
    text = "".join(block.text for block in message.content if hasattr(block, "text")).strip()
    return text or None


def answer_question(question: str, result: PipelineResult) -> str:
    summary = build_summary(result)
    llm_answer = _anthropic_answer(question, summary)
    if llm_answer:
        return llm_answer
    return _fallback_answer(question, summary)
