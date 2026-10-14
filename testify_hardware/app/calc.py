"""Calculele de business: salarii, marjă, taxe, TVA, rapoarte lunare și evoluție.

Modelul urmează raportul contabil al firmei: profitul se calculează din marja brută
(venituri minus costul mărfii vândute), nu din achizițiile de marfă, iar sumele de
contribuții și impozite se rotunjesc la leu, ca în statele de plată.
"""

import calendar
import sqlite3
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from . import inventory
from .db import get_settings
from .fiscal import RATE_KEYS, settings_for_month

MONTH_NAMES = [
    "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]
SALARY_CATEGORY = "Salarii nete"
TAX_CATEGORY = "Taxe și contribuții"
COGS_CATEGORY = "Costul mărfii vândute"
FLOW_MAX_ITEMS = 9


def r2(value: float) -> float:
    return round(value + 0.0, 2)


def rnd(value: float, places: int = 0) -> float:
    """Rotunjire „ca în Excel”: 0,5 se rotunjește în sus, nu la cifra pară."""
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(str(round(value, 9))).quantize(quantum, rounding=ROUND_HALF_UP))


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
    """Din salariul brut: rețineri, net și cost pentru firmă, rotunjite la leu."""
    cas = rnd(gross * rate(settings, "cas_rate"))
    cass = rnd(gross * rate(settings, "cass_rate"))
    taxable = gross - cas - cass
    income_tax = rnd(max(taxable, 0) * rate(settings, "income_tax_rate"))
    cam = rnd(gross * rate(settings, "cam_rate"))
    return {
        "gross": r2(gross),
        "cas": cas,
        "cass": cass,
        "income_tax": income_tax,
        "net": r2(taxable - income_tax),
        "cam": cam,
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


def payroll(conn: sqlite3.Connection, ym: str) -> dict:
    settings = settings_for_month(conn, ym)
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


def vat_rate_for(kind: str, settings: dict) -> float:
    if kind == "reduced":
        return rate(settings, "vat_reduced_rate")
    if kind == "none":
        return 0.0
    return rate(settings, "vat_standard_rate")


def vat_summary(conn: sqlite3.Connection, start: str, end: str, settings: dict) -> dict:
    """TVA colectată din vânzări și deductibilă din achiziții și cheltuieli (pe fiecare document)."""
    standard = rate(settings, "vat_standard_rate")
    collected = sum(rnd(row["amount"] * standard, 2) for row in conn.execute(
        "SELECT amount FROM sales WHERE date BETWEEN ? AND ?", (start, end)))
    on_purchases = sum(rnd(row["quantity"] * row["unit_cost"] * standard, 2) for row in conn.execute(
        "SELECT quantity, unit_cost FROM purchases WHERE date BETWEEN ? AND ?", (start, end)))
    on_expenses = sum(rnd(row["amount"] * vat_rate_for(row["vat_kind"], settings), 2)
                      for row in conn.execute(
        "SELECT amount, vat_kind FROM expenses WHERE date BETWEEN ? AND ?", (start, end)))
    deductible = on_purchases + on_expenses
    return {
        "collected": r2(collected),
        "deductible_purchases": r2(on_purchases),
        "deductible_expenses": r2(on_expenses),
        "deductible": r2(deductible),
        "payable": r2(collected - deductible),
    }


def month_summary(conn: sqlite3.Connection, ym: str, until_day: int | None = None) -> dict:
    """Totalurile unei luni, în structura contului de profit și pierdere.

    Cu until_day se iau doar documentele până în acea zi, ca luna în curs să fie
    comparată cu aceeași perioadă din luna trecută.
    """
    settings = settings_for_month(conn, ym)
    start, end = month_bounds(ym)
    if until_day is not None:
        end = min(end, f"{ym}-{until_day:02d}")

    sales = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS revenue, COUNT(*) AS n, "
        "COALESCE(SUM(COALESCE(quantity, 1) * COALESCE(unit_cost, 0)), 0) AS cogs "
        "FROM sales WHERE date BETWEEN ? AND ?", (start, end)).fetchone()
    revenue, cogs = sales["revenue"], sales["cogs"]
    gross_margin = revenue - cogs

    expense_rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE date BETWEEN ? AND ? GROUP BY category ORDER BY total DESC",
        (start, end),
    ).fetchall()
    expenses_by_category = {row["category"]: r2(row["total"]) for row in expense_rows}
    operating_expenses = sum(expenses_by_category.values())
    purchases = conn.execute(
        "SELECT COALESCE(SUM(quantity * unit_cost), 0) FROM purchases WHERE date BETWEEN ? AND ?",
        (start, end)).fetchone()[0]

    pay = payroll(conn, ym)["totals"]
    opex_total = operating_expenses + pay["employer_cost"]
    profit_before_tax = gross_margin - opex_total
    regime = settings.get("tax_regime", "profit")
    if regime == "micro":
        company_tax = rnd(revenue * rate(settings, "micro_tax_rate"))
    else:
        company_tax = max(0.0, rnd(profit_before_tax * rate(settings, "profit_tax_rate")))
    salary_taxes = pay["cas"] + pay["cass"] + pay["income_tax"] + pay["cam"]
    profit = profit_before_tax - company_tax
    dividend_tax = max(profit, 0) * rate(settings, "dividend_tax_rate")
    vat_payer = settings.get("vat_payer", "1") == "1"

    return {
        "month": ym,
        "label": month_label(ym),
        "revenue": r2(revenue),
        "sales_count": sales["n"],
        "cogs": r2(cogs),
        "gross_margin": r2(gross_margin),
        "gross_margin_pct": r2(gross_margin / revenue * 100) if revenue else 0.0,
        "purchases": r2(purchases),
        "operating_expenses": r2(operating_expenses),
        "expenses_by_category": expenses_by_category,
        "payroll": pay,
        "opex_total": r2(opex_total),
        "taxes": {
            "cas": pay["cas"],
            "cass": pay["cass"],
            "income_tax": pay["income_tax"],
            "cam": pay["cam"],
            "company_tax": r2(company_tax),
            "total": r2(salary_taxes + company_tax),
        },
        "vat_payer": vat_payer,
        "vat": vat_summary(conn, start, end, settings) if vat_payer else None,
        "tax_regime": regime,
        "rates": {key: settings[key] for key in RATE_KEYS},
        "fiscal_rule": settings["fiscal_rule"],
        "company_tax_label": company_tax_label(regime),
        "total_costs": r2(cogs + opex_total + company_tax),
        "profit_before_tax": r2(profit_before_tax),
        "profit": r2(profit),
        "margin": r2(profit / revenue * 100) if revenue else 0.0,
        "dividend_tax": r2(dividend_tax),
        "owner_income": r2(max(profit, 0) - dividend_tax),
        "stock_value": inventory.stock_value(conn, end),
    }


def company_tax_label(regime: str) -> str:
    return "Impozit microîntreprindere" if regime == "micro" else "Impozit pe profit"


def pct_change(current: float, previous: float):
    if not previous:
        return None
    return r2((current - previous) / abs(previous) * 100)


def money_flow(summary: dict, categories: dict) -> list[dict]:
    """„Unde se duc banii”: toate costurile lunii, pe categorii (fără TVA, care nu e cost)."""
    flow = [
        {"name": name, "amount": amount, "color": categories.get(name, "#94a3b8")}
        for name, amount in summary["expenses_by_category"].items()
    ]
    if summary["cogs"]:
        flow.append({"name": COGS_CATEGORY, "amount": summary["cogs"], "color": "#3b82f6"})
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


def receivables(conn: sqlite3.Connection, day: str | None = None) -> dict:
    """Facturile neîncasate (cu TVA), pe clienți, cu cele trecute de scadență."""
    day = day or date.today().isoformat()
    settings = settings_for_month(conn, day[:7])
    vat = rate(settings, "vat_standard_rate") if settings.get("vat_payer", "1") == "1" else 0
    rows = conn.execute(
        "SELECT s.*, c.name AS client_name FROM sales s LEFT JOIN clients c ON c.id = s.client_id "
        "WHERE s.paid = 0 ORDER BY s.due_date").fetchall()
    by_client: dict[str, dict] = {}
    invoices = []
    total = overdue = 0.0
    for row in rows:
        amount = r2(row["amount"] + rnd(row["amount"] * vat, 2))
        late = bool(row["due_date"] and row["due_date"] < day)
        name = row["client_name"] or "Fără client"
        invoices.append({"id": row["id"], "invoice_number": row["invoice_number"], "date": row["date"],
                         "due_date": row["due_date"], "client_name": name, "amount": amount,
                         "overdue": late})
        entry = by_client.setdefault(name, {"client": name, "amount": 0.0, "overdue": 0.0,
                                            "invoices": 0, "oldest_due": row["due_date"]})
        entry["amount"] = r2(entry["amount"] + amount)
        entry["invoices"] += 1
        if late:
            entry["overdue"] = r2(entry["overdue"] + amount)
            overdue += amount
        total += amount
    clients = sorted(by_client.values(), key=lambda item: item["amount"], reverse=True)
    return {"total": r2(total), "overdue": r2(overdue), "clients": clients, "count": len(rows),
            "invoices": invoices}


def payables(conn: sqlite3.Connection, day: str | None = None, soon_days: int = 7) -> dict:
    """Ce are firma de plătit furnizorilor de marfă (cu TVA): restanțe și scadențe apropiate."""
    day = day or date.today().isoformat()
    soon = (date.fromisoformat(day) + timedelta(days=soon_days)).isoformat()
    settings = settings_for_month(conn, day[:7])
    vat = rate(settings, "vat_standard_rate") if settings.get("vat_payer", "1") == "1" else 0
    rows = conn.execute(
        "SELECT pu.*, p.name AS product_name FROM purchases pu JOIN products p ON p.id = pu.product_id "
        "WHERE pu.paid = 0 ORDER BY pu.due_date, pu.id").fetchall()
    by_supplier: dict[str, dict] = {}
    documents = []
    total = overdue = due_soon = 0.0
    for row in rows:
        net = row["quantity"] * row["unit_cost"]
        amount = r2(net + rnd(net * vat, 2))
        late = bool(row["due_date"] and row["due_date"] < day)
        near = bool(row["due_date"] and day <= row["due_date"] <= soon)
        name = row["supplier"] or "Fără furnizor"
        documents.append({"id": row["id"], "doc_number": row["doc_number"], "date": row["date"],
                          "due_date": row["due_date"], "supplier": name, "product": row["product_name"],
                          "amount": amount, "overdue": late, "due_soon": near})
        entry = by_supplier.setdefault(name, {"supplier": name, "amount": 0.0, "overdue": 0.0,
                                              "due_soon": 0.0, "documents": 0, "next_due": row["due_date"]})
        entry["amount"] = r2(entry["amount"] + amount)
        entry["documents"] += 1
        total += amount
        if late:
            entry["overdue"] = r2(entry["overdue"] + amount)
            overdue += amount
        if near:
            entry["due_soon"] = r2(entry["due_soon"] + amount)
            due_soon += amount
    suppliers = sorted(by_supplier.values(), key=lambda item: item["amount"], reverse=True)
    return {"total": r2(total), "overdue": r2(overdue), "due_soon": r2(due_soon), "soon_days": soon_days,
            "suppliers": suppliers, "documents": documents, "count": len(rows)}


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
    if current["revenue"] and current["cogs"]:
        notes.append({
            "tone": "info",
            "icon": "box",
            "text": f"Marja brută: {fmt_pct(current['gross_margin_pct'])}. Din fiecare 100 lei "
                    f"vânduți, {100 - current['gross_margin_pct']:.0f} lei sunt costul mărfii.",
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
        tone = "good" if current["margin"] >= 10 else "warn" if current["margin"] >= 0 else "bad"
        notes.append({
            "tone": tone,
            "icon": "percent",
            "text": f"Din fiecare 100 lei încasați, firmei îi rămân "
                    f"{current['margin']:.0f} lei profit net.",
        })
    with_revenue = [m for m in trend if m["revenue"]]
    if len(with_revenue) >= 3:
        best = max(with_revenue, key=lambda m: m["profit"])
        notes.append({
            "tone": "info",
            "icon": "star",
            "text": f"Cea mai bună lună din perioadă: {best['label']}, "
                    f"cu un profit de {fmt(best['profit'])}.",
        })
    return notes


def first_data_month(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT MIN(d) FROM (SELECT MIN(date) AS d FROM sales UNION ALL "
        "SELECT MIN(date) FROM expenses UNION ALL SELECT MIN(date) FROM purchases)").fetchone()
    return row[0][:7] if row and row[0] else None


def dashboard(conn: sqlite3.Connection, ym: str) -> dict:
    settings = get_settings(conn)
    categories = {row["name"]: row["color"]
                  for row in conn.execute("SELECT name, color FROM categories")}
    current = month_summary(conn, ym)
    in_progress = ym == current_month()
    until_day = date.today().day if in_progress else None
    previous = month_summary(conn, shift_month(ym, -1), until_day)

    # Evoluția: cel mult 12 luni, de la prima lună cu date (dar măcar 3 luni pe grafic).
    first = first_data_month(conn) or ym
    span = max(3, min(12, (int(ym[:4]) * 12 + int(ym[5:])) - (int(first[:4]) * 12 + int(first[5:])) + 1))
    trend = []
    for offset in range(-(span - 1), 1):
        month = shift_month(ym, offset)
        summary = current if month == ym else month_summary(conn, month)
        trend.append({
            "month": month,
            "label": month_label(month, short=True),
            "revenue": summary["revenue"],
            "gross_margin": summary["gross_margin"],
            "costs": summary["total_costs"],
            "profit": summary["profit"],
            "taxes": summary["taxes"]["total"],
            "salary_taxes": r2(summary["taxes"]["total"] - summary["taxes"]["company_tax"]),
            "company_tax": summary["taxes"]["company_tax"],
            "vat_payable": summary["vat"]["payable"] if summary["vat"] else 0,
            "stock_value": summary["stock_value"],
        })

    start, end = month_bounds(ym)
    top_products = [
        dict(row) for row in conn.execute(
            "SELECT COALESCE(p.name, s.product) AS product, SUM(COALESCE(s.quantity, 1)) AS quantity, "
            "SUM(s.amount) AS amount, "
            "SUM(s.amount - COALESCE(s.quantity, 1) * COALESCE(s.unit_cost, 0)) AS profit "
            "FROM sales s LEFT JOIN products p ON p.id = s.product_id "
            "WHERE s.date BETWEEN ? AND ? AND COALESCE(p.name, s.product) IS NOT NULL "
            "GROUP BY 1 ORDER BY profit DESC LIMIT 5",
            (start, end),
        )
    ]
    top_clients = [
        dict(row) for row in conn.execute(
            "SELECT c.name AS client, c.type AS type, SUM(s.amount) AS amount, COUNT(*) AS invoices "
            "FROM sales s JOIN clients c ON c.id = s.client_id WHERE s.date BETWEEN ? AND ? "
            "GROUP BY c.id ORDER BY amount DESC LIMIT 5", (start, end))
    ]
    products = inventory.products_overview(conn)
    low_stock = [p for p in products if p["status"] != "ok" and p["active"]]
    flow = money_flow(current, categories)
    year_to_date = [m for m in trend if m["month"][:4] == ym[:4]]

    return {
        "company": settings.get("company_name", "Testify Hardware"),
        "owner_name": settings.get("owner_name", ""),
        "in_progress": in_progress,
        "compared_until_day": until_day,
        "current": current,
        "previous": previous,
        "changes": {
            "revenue": pct_change(current["revenue"], previous["revenue"]),
            "gross_margin": pct_change(current["gross_margin"], previous["gross_margin"]),
            "total_costs": pct_change(current["total_costs"], previous["total_costs"]),
            "profit": pct_change(current["profit"], previous["profit"]),
            "owner_income": pct_change(current["owner_income"], previous["owner_income"]),
        },
        "trend": trend,
        "flow": flow,
        "top_products": top_products,
        "top_clients": top_clients,
        "low_stock": low_stock,
        "receivables": receivables(conn),
        "payables": payables(conn),
        "insights": insights(current, previous, trend, flow, until_day),
        "year": {
            "revenue": r2(sum(m["revenue"] for m in year_to_date)),
            "costs": r2(sum(m["costs"] for m in year_to_date)),
            "profit": r2(sum(m["profit"] for m in year_to_date)),
        },
    }
