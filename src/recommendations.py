"""
Sales recommendations — data-driven observations from this CSV's own
aggregates, plus a fixed block of sourced Romanian market context.

Every number in a data-driven recommendation comes from
`data_pipeline.run_pipeline`'s deterministic aggregates, never from a model.
The market-context numbers are real published figures (see MARKET_CONTEXT),
current as of September 2026 — they don't change per upload.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from data_pipeline import PipelineResult

_ENTITY_KEYWORDS = ("client", "vanzator", "vânzător", "customer", "nume")
_CURRENCY_KEYWORDS = ("valuta", "moneda", "monedă", "currency")

MARKET_CONTEXT = [
    {
        "title": "Inflație 6,2% — cea mai mare din UE",
        "detail": (
            "Rata anuală a inflației a scăzut la 6,17–6,2% în august 2026, dar România "
            "rămâne pe primul loc în UE. Contracte cu preț fix pierd valoare reală lună de "
            "lună — merită o clauză de recalculare anuală legată de IPC."
        ),
        "source": "https://agerpres.ro/economic/2026/09/11/rata-anuala-a-inflatiei-a-scazut-la-6-17-in-luna-august--1592562",
    },
    {
        "title": "Dobânda BNR la 6,50% — credit scump",
        "detail": (
            "Rata de politică monetară a rămas la 6,50% pe tot parcursul lui 2026. Clienții "
            "amână investițiile finanțate prin credit — produsele cu plată eșalonată/mică "
            "lunar sunt mai ușor de aprobat decât proiectele mari, one-off."
        ),
        "source": "https://www.digi24.ro/stiri/actualitate/bnr-mentine-dobanda-cheie-la-650-in-prima-sedinta-de-politica-monetara-din-2026-3591757",
    },
    {
        "title": "Încredere IMM în scădere",
        "detail": (
            "Indexul antreprenorial a scăzut la 43,25 puncte; doar 6% dintre antreprenori se "
            "așteaptă la o evoluție economică pozitivă. Ciclurile de vânzare se pot lungi — "
            "urmărește proactiv clienții cu semnale de ezitare."
        ),
        "source": "https://www.bursa.ro/sondaj-imm-romania-10-procente-dintre-antreprenori-iau-in-calcul-inchiderea-firmei-01451955",
    },
    {
        "title": "Piața IT crește 12%, dar doar 5% folosesc AI",
        "detail": (
            "Industria de servicii IT din România crește ~12% anual, dar adopția AI e sub 5%. "
            "E un gol de piață clar pentru orice ofertă care ajută clienții să adopte AI, nu "
            "doar să crească volumul."
        ),
        "source": "https://news24.ro/piata-it-din-romania-in-2026-doar-5-dintre-companii-folosesc-ai/",
    },
]


def _find_column(candidates: list[str], keywords: tuple[str, ...]) -> str | None:
    for col in candidates:
        if any(k in col.strip().lower() for k in keywords):
            return col
    return None


def _concentration_insight(result: PipelineResult) -> dict[str, Any] | None:
    top_by = result.aggregates.get("top_by", {})
    value_col = result.aggregates.get("value_column")
    if not top_by or not value_col:
        return None

    entity_col = _find_column(list(top_by.keys()), _ENTITY_KEYWORDS) or next(iter(top_by))
    entries = top_by.get(entity_col) or []
    if len(entries) < 2:
        return None

    total = sum(e["value"] for e in entries)
    if total <= 0:
        return None
    leader = entries[0]
    share = leader["value"] / total * 100
    gap = (leader["value"] / entries[1]["value"] - 1) * 100 if entries[1]["value"] > 0 else 0

    if share < 20:
        return None
    return {
        "title": f"Concentrare mare pe „{leader['key']}”",
        "detail": (
            f"„{leader['key']}” reprezintă {share:.0f}% din „{value_col}” din top {entity_col} "
            f"— cu {gap:.0f}% peste locul 2 ({entries[1]['key']}). Dacă acest {entity_col.lower()} "
            f"pleacă sau reduce comenzile, pierzi o parte semnificativă din venit. Diversifică "
            f"activ în restul din top {min(len(entries), 5)}."
        ),
    }


def _currency_insight(result: PipelineResult) -> dict[str, Any] | None:
    top_by = result.aggregates.get("top_by", {})
    value_col = result.aggregates.get("value_column")
    currency_col = _find_column(list(top_by.keys()), _CURRENCY_KEYWORDS)
    if not currency_col or not value_col:
        return None

    entries = top_by.get(currency_col) or []
    if len(entries) < 2:
        return None
    total = sum(e["value"] for e in entries)
    if total <= 0:
        return None
    leader = entries[0]
    share = leader["value"] / total * 100
    if share < 70:
        return None
    return {
        "title": f"Venit concentrat în {leader['key']} ({share:.0f}%)",
        "detail": (
            f"Aproape tot venitul e într-o singură monedă ({leader['key']}), fără hedging. "
            f"Cu inflația locală ridicată, ia în calcul facturarea în altă monedă pentru "
            f"contractele noi/mari, ca diversificare parțială a riscului valutar."
        ),
    }


def _monthly_trend_insight(result: PipelineResult) -> dict[str, Any] | None:
    value_col = result.aggregates.get("value_column")
    date_col = next((c for c, r in result.roles.items() if r == "date"), None)
    if not value_col or not date_col:
        return None

    monthly: dict[str, float] = defaultdict(float)
    for row in result.table:
        date_val = row.get(date_col)
        value = row.get(value_col)
        if not date_val or value is None:
            continue
        month = str(date_val)[:7]  # YYYY-MM
        monthly[month] += value

    if len(monthly) < 3:
        return None
    low_month, low_value = min(monthly.items(), key=lambda kv: kv[1])
    high_month, high_value = max(monthly.items(), key=lambda kv: kv[1])
    if high_value <= 0:
        return None
    return {
        "title": f"Minim de vânzări în {low_month}",
        "detail": (
            f"„{value_col}” a fost cel mai mic în {low_month} ({low_value:,.2f}) și cel mai "
            f"mare în {high_month} ({high_value:,.2f}). Dacă tiparul se repetă, programează "
            f"campanii/renewals înainte de luna slabă, nu reactiv."
        ),
    }


def _anomaly_insight(result: PipelineResult) -> dict[str, Any] | None:
    if not result.anomalies:
        return None
    biggest = max(result.anomalies, key=lambda a: abs(a["value"]))
    return {
        "title": f"{len(result.anomalies)} valori neobișnuite de verificat",
        "detail": (
            f"Cea mai mare e pe „{biggest['column']}” = {biggest['value']:,.2f} (rând "
            f"{biggest['row'] + 1}). Verifică dacă e o eroare de date sau o oportunitate reală "
            f"de vânzare mare — dacă e reală, poate deveni caz de succes de replicat."
        ),
    }


def generate_recommendations(result: PipelineResult) -> dict[str, Any]:
    data_driven = [
        insight
        for insight in (
            _concentration_insight(result),
            _currency_insight(result),
            _monthly_trend_insight(result),
            _anomaly_insight(result),
        )
        if insight is not None
    ]
    return {"data_driven": data_driven, "market_context": MARKET_CONTEXT}
