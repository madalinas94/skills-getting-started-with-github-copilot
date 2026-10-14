"""Calculele de business: salarii, taxe, rapoarte lunare și evoluție."""

import calendar
import sqlite3
from datetime import date

from .db import get_settings

MONTH_NAMES = [
    "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]
SALARY_CATEGORY = "Salarii nete"
TAX_CATEGORY = "Taxe și contribuții"
FLOW_MAX_ITEMS = 9


def r2(value: float) -> float:
    return round(value + 0.0, 2)


def month_bounds(ym: str) -> tuple[str, str]:
    year, month = (int(part) for part in ym.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def shift_month(ym: str, delta: int) -> str:
    year, month = (int(part) for part in ym.split("-"))
    index = year * 12 + (month - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_label(ym: str, short: bool = False) -> str:
    year, month = (int(part) for part in ym.split("-"))
    name = MONTH_NAMES[month - 1]
    return f"{name[:3]} {str(year)[2:]}" if short else f"{name} {year}"


def current_month() -> str:
    return date.today().strftime("%Y-%m")


def rate(settings: dict, key: str) -> float:
    return float(settings.get(key, 0)) / 100


def salary_breakdown(gross: float, settings: dict) -> dict:
    """Din salariul brut calculează reținerile, netul și costul total pentru firmă."""
    cas = gross * rate(settings, "cas_rate")
    cass = gross * rate(settings, "cass_rate")
    income_tax = max(0.0, gross - cas - cass) * rate(settings, "income_tax_rate")
    cam = gross * rate(settings, "cam_rate")
    return {
        "gross": r2(gross),
        "cas": r2(cas),
        "cass": r2(cass),
        "income_tax": r2(income_tax),
        "net": r2(gross - cas - cass - income_tax),
        "cam": r2(cam),
        "employer_cost": r2(gross + cam),
    }


def gross_for_month(conn: sqlite3.Connection, employee: sqlite3.Row, ym: str):
    """Salariul brut valabil în luna dată sau None dacă angajatul nu era activ."""
    start, end = month_bounds(ym)
    if employee["hire_date"] > end:
        return None
    if employee["end_date"] and employee["end_date"] < start:
        return None
    row = conn.execute(
        "SELECT gross FROM salary_history WHERE employee_id = ? AND effective_from <= ? "
        "ORDER BY effective_from DESC, id DESC LIMIT 1",
        (employee["id"], end),
    ).fetchone()
    return row["gross"] if row else None


def payroll(conn: sqlite3.Connection, ym: str, settings: dict | None = None) -> dict:
    settings = settings or get_settings(conn)
    lines = []
    for employee in conn.execute("SELECT * FROM employees ORDER BY name").fetchall():
        gross = gross_for_month(conn, employee, ym)
        if gross is None:
            continue
        lines.append(
            {"employee_id": employee["id"], "name": employee["name"],
             "role": employee["role"], **salary_breakdown(gross, settings)}
        )
    keys = ["gross", "cas", "cass", "income_tax", "net", "cam", "employer_cost"]
    totals = {key: r2(sum(line[key] for line in lines)) for key in keys}
    return {"month": ym, "lines": lines, "totals": totals}


def month_summary(conn: sqlite3.Connection, ym: str, settings: dict | None = None,
                  until_day: int | None = None) -> dict:
    """Totalurile unei luni: venituri, cheltuieli, salarii, taxe, profit.

    Cu until_day se iau doar vânzările și cheltuielile până în acea zi, ca luna
    în curs să fie comparată cu aceeași perioadă din luna trecută.
    """
    settings = settings or get_settings(conn)
    start, end = month_bounds(ym)
    if until_day is not None:
        end = min(end, f"{ym}-{until_day:02d}")

    revenue = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM sales WHERE date BETWEEN ? AND ?",
        (start, end),
    ).fetchone()[0]
    sales_count = conn.execute(
        "SELECT COUNT(*) FROM sales WHERE date BETWEEN ? AND ?", (start, end)
    ).fetchone()[0]
    expense_rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE date BETWEEN ? AND ? GROUP BY category ORDER BY total DESC",
        (start, end),
    ).fetchall()
    expenses_by_category = {row["category"]: r2(row["total"]) for row in expense_rows}
    operating_expenses = sum(expenses_by_category.values())

    pay = payroll(conn, ym, settings)["totals"]
    micro_tax = revenue * rate(settings, "micro_tax_rate")
    salary_taxes = pay["cas"] + pay["cass"] + pay["income_tax"] + pay["cam"]
    total_taxes = salary_taxes + micro_tax
    total_costs = operating_expenses + pay["employer_cost"] + micro_tax
    profit = revenue - total_costs
    dividend_tax = max(profit, 0) * rate(settings, "dividend_tax_rate")

    return {
        "month": ym,
        "label": month_label(ym),
        "revenue": r2(revenue),
        "sales_count": sales_count,
        "operating_expenses": r2(operating_expenses),
        "expenses_by_category": expenses_by_category,
        "payroll": pay,
        "taxes": {
            "cas": pay["cas"],
            "cass": pay["cass"],
            "income_tax": pay["income_tax"],
            "cam": pay["cam"],
            "micro_tax": r2(micro_tax),
            "total": r2(total_taxes),
        },
        "total_costs": r2(total_costs),
        "profit": r2(profit),
        "margin": r2(profit / revenue * 100) if revenue else 0.0,
        "dividend_tax": r2(dividend_tax),
        "owner_income": r2(max(profit, 0) - dividend_tax),
    }


def pct_change(current: float, previous: float):
    if not previous:
        return None
    return r2((current - previous) / abs(previous) * 100)


def money_flow(summary: dict, categories: dict) -> list[dict]:
    """„Unde se duc banii”: toate ieșirile de bani dintr-o lună, pe categorii."""
    flow = [
        {"name": name, "amount": amount, "color": categories.get(name, "#94a3b8")}
        for name, amount in summary["expenses_by_category"].items()
    ]
    if summary["payroll"]["net"]:
        flow.append({"name": SALARY_CATEGORY, "amount": summary["payroll"]["net"],
                     "color": "#22d3ee"})
    if summary["taxes"]["total"]:
        flow.append({"name": TAX_CATEGORY, "amount": summary["taxes"]["total"],
                     "color": "#f87171"})
    flow.sort(key=lambda item: item["amount"], reverse=True)
    # Cu multe categorii, graficul rămâne lizibil: cele mici se adună într-o felie.
    if len(flow) > FLOW_MAX_ITEMS:
        rest = flow[FLOW_MAX_ITEMS - 1:]
        flow = flow[:FLOW_MAX_ITEMS - 1] + [{
            "name": f"Alte {len(rest)} categorii",
            "amount": r2(sum(item["amount"] for item in rest)),
            "color": "#64748b",
            "details": [{"name": item["name"], "amount": item["amount"]} for item in rest],
        }]
    total = sum(item["amount"] for item in flow) or 1
    for item in flow:
        item["share"] = r2(item["amount"] / total * 100)
    return flow


def fmt(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".") + " lei"


def fmt_pct(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + "%"


def insights(current: dict, previous: dict, trend: list[dict], flow: list[dict],
             until_day: int | None = None) -> list[dict]:
    """Observații scurte, în limbaj simplu, pentru antreprenor."""
    notes = []
    change = pct_change(current["revenue"], previous["revenue"])
    if change is not None:
        direction = "au crescut" if change >= 0 else "au scăzut"
        period = (f"primele {until_day} zile din {month_label(previous['month'])}"
                  if until_day else month_label(previous["month"]))
        notes.append({
            "tone": "good" if change >= 0 else "bad",
            "icon": "trend",
            "text": f"Vânzările {direction} cu {fmt_pct(abs(change))} față de {period}.",
        })
    if flow:
        top = flow[0]
        notes.append({
            "tone": "info",
            "icon": "wallet",
            "text": f"Cei mai mulți bani se duc pe „{top['name']}”: "
                    f"{fmt(top['amount'])} ({top['share']:.0f}% din ieșiri).",
        })
    # O cheltuială care crește mai repede decât vânzările merită semnalată.
    revenue_growth = change or 0
    increases = []
    for name, amount in current["expenses_by_category"].items():
        before = previous["expenses_by_category"].get(name, 0)
        growth = pct_change(amount, before) if before else None
        if growth is not None and growth > max(15, revenue_growth + 10) and amount - before > 200:
            increases.append((amount - before, name, pct_change(amount, before)))
    if increases:
        diff, name, pct = max(increases)
        notes.append({
            "tone": "warn",
            "icon": "alert",
            "text": f"Atenție: cheltuielile cu „{name}” au crescut cu {pct:.0f}% "
                    f"(+{fmt(diff)}) față de "
                    f"{'aceeași perioadă a lunii trecute' if until_day else 'luna trecută'}.",
        })
    if current["revenue"] and not until_day:
        tone = "good" if current["margin"] >= 15 else "warn" if current["margin"] >= 0 else "bad"
        notes.append({
            "tone": tone,
            "icon": "percent",
            "text": f"Din fiecare 100 lei încasați, firmei îi rămân "
                    f"{current['margin']:.0f} lei profit.",
        })
    with_revenue = [m for m in trend if m["revenue"]]
    if len(with_revenue) >= 3:
        best = max(with_revenue, key=lambda m: m["profit"])
        notes.append({
            "tone": "info",
            "icon": "star",
            "text": f"Cea mai bună lună din ultimul an: {best['label']}, "
                    f"cu un profit de {fmt(best['profit'])}.",
        })
    return notes


def dashboard(conn: sqlite3.Connection, ym: str) -> dict:
    settings = get_settings(conn)
    categories = {row["name"]: row["color"]
                  for row in conn.execute("SELECT name, color FROM categories")}
    current = month_summary(conn, ym, settings)
    in_progress = ym == current_month()
    until_day = date.today().day if in_progress else None
    previous = month_summary(conn, shift_month(ym, -1), settings, until_day)

    trend = []
    for offset in range(-11, 1):
        month = shift_month(ym, offset)
        summary = month_summary(conn, month, settings)
        trend.append({
            "month": month,
            "label": month_label(month, short=True),
            "revenue": summary["revenue"],
            "costs": summary["total_costs"],
            "profit": summary["profit"],
            "taxes": summary["taxes"]["total"],
            "salary_taxes": r2(summary["taxes"]["total"] - summary["taxes"]["micro_tax"]),
            "micro_tax": summary["taxes"]["micro_tax"],
        })

    start, end = month_bounds(ym)
    top_products = [
        dict(row) for row in conn.execute(
            "SELECT product, SUM(COALESCE(quantity, 1)) AS quantity, SUM(amount) AS amount "
            "FROM sales WHERE date BETWEEN ? AND ? AND product IS NOT NULL AND product != '' "
            "GROUP BY product ORDER BY amount DESC LIMIT 5",
            (start, end),
        )
    ]
    flow = money_flow(current, categories)
    year_to_date = [m for m in trend if m["month"][:4] == ym[:4]]

    return {
        "company": settings.get("company_name", "Testify Hardware"),
        "in_progress": in_progress,
        "compared_until_day": until_day,
        "current": current,
        "previous": previous,
        "changes": {
            "revenue": pct_change(current["revenue"], previous["revenue"]),
            "total_costs": pct_change(current["total_costs"], previous["total_costs"]),
            "profit": pct_change(current["profit"], previous["profit"]),
            "owner_income": pct_change(current["owner_income"], previous["owner_income"]),
        },
        "trend": trend,
        "flow": flow,
        "top_products": top_products,
        "insights": insights(current, previous, trend, flow, until_day),
        "year": {
            "revenue": r2(sum(m["revenue"] for m in year_to_date)),
            "costs": r2(sum(m["costs"] for m in year_to_date)),
            "profit": r2(sum(m["profit"] for m in year_to_date)),
        },
    }
