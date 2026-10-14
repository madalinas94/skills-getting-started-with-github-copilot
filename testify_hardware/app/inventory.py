"""Produse și stoc: stocul se calculează din stocul de deschidere, recepții (NIR) și vânzări."""

import sqlite3
from datetime import date, timedelta

STOCK_SQL = """
SELECT p.*,
  (CASE WHEN p.opening_date IS NULL OR p.opening_date <= :day THEN p.opening_stock ELSE 0 END)
  + COALESCE((SELECT SUM(quantity) FROM purchases pu WHERE pu.product_id = p.id
      AND pu.date <= :day AND (p.opening_date IS NULL OR pu.date >= p.opening_date)), 0)
  - COALESCE((SELECT SUM(quantity) FROM sales s WHERE s.product_id = p.id
      AND s.date <= :day AND (p.opening_date IS NULL OR s.date >= p.opening_date)), 0)
  AS stock
FROM products p
"""


def stock_on(conn: sqlite3.Connection, day: str) -> dict[int, int]:
    """Stocul fiecărui produs la sfârșitul zilei date."""
    return {row["id"]: row["stock"] for row in conn.execute(STOCK_SQL, {"day": day})}


def stock_value(conn: sqlite3.Connection, day: str) -> float:
    rows = conn.execute(STOCK_SQL, {"day": day}).fetchall()
    return round(sum(max(row["stock"], 0) * row["cost"] for row in rows), 2)


def stock_status(stock: int, min_stock: int) -> str:
    if stock <= 0:
        return "out"
    if stock <= min_stock:
        return "low"
    return "ok"


def products_overview(conn: sqlite3.Connection, today: str | None = None) -> list[dict]:
    """Lista produselor cu stoc, valoare, vânzări recente și estimarea zilelor de stoc."""
    today = today or date.today().isoformat()
    since = (date.fromisoformat(today) - timedelta(days=30)).isoformat()
    sold_30 = {row["product_id"]: row["qty"] for row in conn.execute(
        "SELECT product_id, SUM(quantity) AS qty FROM sales "
        "WHERE product_id IS NOT NULL AND date > ? AND date <= ? GROUP BY product_id",
        (since, today))}
    # Dacă în ultimele 30 de zile nu s-a vândut nimic (de exemplu date importate mai vechi),
    # ritmul de vânzare se estimează din ultima lună cu vânzări.
    if not sold_30:
        last = conn.execute("SELECT MAX(date) FROM sales WHERE product_id IS NOT NULL").fetchone()[0]
        if last:
            since = (date.fromisoformat(last) - timedelta(days=30)).isoformat()
            sold_30 = {row["product_id"]: row["qty"] for row in conn.execute(
                "SELECT product_id, SUM(quantity) AS qty FROM sales "
                "WHERE product_id IS NOT NULL AND date > ? AND date <= ? GROUP BY product_id",
                (since, last))}

    result = []
    for row in conn.execute(STOCK_SQL + " ORDER BY p.category, p.name", {"day": today}):
        sold = sold_30.get(row["id"], 0)
        daily = sold / 30
        stock = row["stock"]
        margin = row["sale_price"] - row["cost"]
        result.append({
            "id": row["id"], "code": row["code"], "name": row["name"],
            "category": row["category"], "supplier": row["supplier"],
            "sale_price": row["sale_price"], "cost": row["cost"],
            "margin_pct": round(margin / row["sale_price"] * 100, 1) if row["sale_price"] else 0,
            "min_stock": row["min_stock"], "stock": stock,
            "stock_value": round(max(stock, 0) * row["cost"], 2),
            "status": stock_status(stock, row["min_stock"]),
            "sold_30": sold,
            "days_left": int(stock / daily) if daily > 0 and stock > 0 else None,
            "opening_stock": row["opening_stock"], "opening_date": row["opening_date"],
            "active": bool(row["active"]),
        })
    return result


def inventory_month(conn: sqlite3.Connection, ym: str) -> dict:
    """Fișa de inventar a lunii: stoc inițial, intrări, ieșiri, stoc final, valoare."""
    from .calc import month_bounds

    start, end = month_bounds(ym)
    before = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
    initial = stock_on(conn, before)
    final = stock_on(conn, end)
    entries = {row["product_id"]: row["qty"] for row in conn.execute(
        "SELECT product_id, SUM(quantity) AS qty FROM purchases WHERE date BETWEEN ? AND ? "
        "GROUP BY product_id", (start, end))}
    exits = {row["product_id"]: row["qty"] for row in conn.execute(
        "SELECT product_id, SUM(quantity) AS qty FROM sales WHERE product_id IS NOT NULL "
        "AND date BETWEEN ? AND ? GROUP BY product_id", (start, end))}
    lines = []
    for product in conn.execute("SELECT * FROM products ORDER BY code"):
        pid = product["id"]
        # Produsele deschise în mijlocul lunii pornesc de la stocul de deschidere.
        opening_inside = product["opening_date"] and start <= product["opening_date"] <= end
        first = product["opening_stock"] if opening_inside else initial.get(pid, 0)
        lines.append({
            "code": product["code"], "name": product["name"], "category": product["category"],
            "initial": first, "entries": entries.get(pid, 0), "exits": exits.get(pid, 0),
            "final": final.get(pid, 0), "cost": product["cost"],
            "value": round(max(final.get(pid, 0), 0) * product["cost"], 2),
        })
    return {
        "month": ym, "lines": lines,
        "totals": {
            "entries": sum(line["entries"] for line in lines),
            "exits": sum(line["exits"] for line in lines),
            "value": round(sum(line["value"] for line in lines), 2),
        },
    }
