"""Testify Hardware — aplicația internă pentru calculul lunar.

Pornire: uvicorn app.main:app --host 0.0.0.0 --port 8000 (din folderul testify_hardware)
"""

import asyncio
import re
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from fastapi import (APIRouter, Cookie, Depends, FastAPI, File, Form, HTTPException, Query,
                     Response, UploadFile)
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import assistant_ai, auth, calc, demo, exports, fiscal, importer, inventory
from .db import DEFAULT_SETTINGS, DEFAULT_SUPPLIER_TERMS, get_conn, get_settings, init_db, set_setting

STATIC_DIR = Path(__file__).resolve().parent / "static"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
VAT_KIND_PATTERN = r"^(standard|reduced|none)$"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def run_fiscal_check() -> dict:
    with get_conn() as conn:
        return fiscal.check_for_updates(conn)


async def fiscal_watcher() -> None:
    """Verifică periodic, în fundal, dacă au apărut reguli fiscale noi."""
    while True:
        await asyncio.to_thread(run_fiscal_check)
        await asyncio.sleep(fiscal.CHECK_INTERVAL_HOURS * 3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    watcher = asyncio.create_task(fiscal_watcher()) if fiscal.feed_url() else None
    yield
    if watcher:
        watcher.cancel()


app = FastAPI(title="Testify Hardware", description="Aplicația internă pentru calculul lunar",
              lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")


def valid_date(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not DATE_RE.match(value):
        raise ValueError("Data trebuie să fie în formatul AAAA-LL-ZZ.")
    date.fromisoformat(value)
    return value


# ---------- Autentificare ----------

class PasswordIn(BaseModel):
    password: str = Field(min_length=4, max_length=200)


class SetupIn(PasswordIn):
    demo: bool = False


class ChangePasswordIn(BaseModel):
    current: str
    new: str = Field(min_length=4, max_length=200)


class RecoverIn(BaseModel):
    code: str = Field(min_length=4, max_length=40)
    password: str = Field(min_length=4, max_length=200)


class CurrentPasswordIn(BaseModel):
    current: str


def start_session(response: Response, conn) -> None:
    token = auth.create_session(conn)
    response.set_cookie(auth.COOKIE_NAME, token, httponly=True, samesite="strict",
                        max_age=60 * 60 * 24 * 30)


@app.get("/api/auth/status")
def auth_status(testify_session: str | None = Cookie(default=None)):
    with get_conn() as conn:
        settings = get_settings(conn)
        return {
            "setup_done": auth.is_setup_done(conn),
            "logged_in": auth.is_valid_session(conn, testify_session),
            "company": settings.get("company_name"),
            "owner_name": settings.get("owner_name", ""),
            "has_recovery": auth.has_recovery_code(conn),
        }


@app.post("/api/auth/setup")
def auth_setup(body: SetupIn, response: Response):
    with get_conn() as conn:
        if auth.is_setup_done(conn):
            raise HTTPException(status_code=400, detail="Parola a fost deja setată.")
        auth.set_password(conn, body.password)
        code = auth.set_recovery_code(conn)
        if body.demo:
            demo.load_demo_data(conn)
        start_session(response, conn)
    return {"ok": True, "recovery_code": code}


@app.post("/api/auth/login")
def auth_login(body: PasswordIn, response: Response):
    auth.limiter.check()
    with get_conn() as conn:
        if not auth.check_password(conn, body.password):
            auth.limiter.failed()
            raise HTTPException(status_code=401, detail="Parolă greșită.")
        auth.limiter.reset()
        start_session(response, conn)
    return {"ok": True}


@app.post("/api/auth/recover")
def auth_recover(body: RecoverIn, response: Response):
    """Parolă uitată: cu codul de recuperare se pune o parolă nouă și se primește un cod nou."""
    auth.limiter.check()
    with get_conn() as conn:
        if not auth.check_recovery_code(conn, body.code):
            auth.limiter.failed()
            raise HTTPException(status_code=400, detail="Codul de recuperare nu este corect.")
        auth.limiter.reset()
        auth.set_password(conn, body.password)
        auth.end_all_sessions(conn)  # cine era conectat cu parola veche iese
        code = auth.set_recovery_code(conn)  # codul folosit nu mai e valabil
        start_session(response, conn)
    return {"ok": True, "recovery_code": code}


@app.post("/api/auth/logout")
def auth_logout(response: Response, testify_session: str | None = Cookie(default=None)):
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (testify_session,))
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}


# Tot ce urmează cere autentificare.
api = APIRouter(prefix="/api", dependencies=[Depends(auth.require_login)])


@api.post("/auth/change-password")
def change_password(body: ChangePasswordIn):
    with get_conn() as conn:
        if not auth.check_password(conn, body.current):
            raise HTTPException(status_code=400, detail="Parola actuală nu este corectă.")
        auth.set_password(conn, body.new)
    return {"ok": True}


@api.post("/auth/recovery-code")
def new_recovery_code(body: CurrentPasswordIn):
    with get_conn() as conn:
        if not auth.check_password(conn, body.current):
            raise HTTPException(status_code=400, detail="Parola actuală nu este corectă.")
        return {"recovery_code": auth.set_recovery_code(conn)}


# ---------- Dashboard și rapoarte ----------

@api.get("/dashboard")
def get_dashboard(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    with get_conn() as conn:
        return calc.dashboard(conn, month)


@api.get("/payroll")
def get_payroll(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    with get_conn() as conn:
        return calc.payroll(conn, month)


@api.get("/summary")
def get_summary(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    with get_conn() as conn:
        return calc.month_summary(conn, month)


@api.get("/export/excel")
def export_excel(month: str = Query(pattern=MONTH_PATTERN)):
    with get_conn() as conn:
        content = exports.excel_report(conn, month)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="raport-{month}.xlsx"'},
    )


@api.get("/export/pdf")
def export_pdf(month: str = Query(pattern=MONTH_PATTERN)):
    with get_conn() as conn:
        content = exports.pdf_report(conn, month)
    return Response(
        content, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="raport-{month}.pdf"'},
    )


# ---------- Vânzări ----------

class SaleIn(BaseModel):
    """O factură pe un produs din stoc sau un total pe zi/lună (fără produs)."""
    date: str
    product_id: int | None = None
    client_id: int | None = None
    quantity: int | None = Field(default=None, ge=1)
    unit_price: float | None = Field(default=None, gt=0)
    amount: float | None = Field(default=None, gt=0)
    cost_total: float | None = Field(default=None, ge=0)
    description: str = Field(default="", max_length=200)
    invoice_number: str | None = Field(default=None, max_length=40)
    paid: bool | None = None

    @field_validator("date")
    @classmethod
    def check_date(cls, value):
        return valid_date(value)


def next_invoice_number(conn) -> str:
    numbers = [int(match.group(1)) for (number,) in conn.execute(
        "SELECT invoice_number FROM sales WHERE invoice_number LIKE 'NB-%'")
        if (match := re.match(r"NB-(\d+)$", number or ""))]
    return f"NB-{max(numbers, default=1000) + 1:04d}"


def sale_values(conn, body: SaleIn) -> dict:
    """Completează o vânzare: preț și cost din produs, scadență din termenul clientului."""
    client = None
    if body.client_id:
        client = conn.execute("SELECT * FROM clients WHERE id = ?", (body.client_id,)).fetchone()
        if not client:
            raise HTTPException(status_code=404, detail="Clientul nu există.")
    terms = client["payment_terms"] if client else 0
    due = (date.fromisoformat(body.date) + timedelta(days=terms)).isoformat()
    values = {"date": body.date, "client_id": body.client_id, "due_date": due,
              "paid": int(body.paid if body.paid is not None else terms == 0)}
    if body.product_id:
        product = conn.execute("SELECT * FROM products WHERE id = ?", (body.product_id,)).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Produsul nu există.")
        quantity = body.quantity or 1
        price = body.unit_price or product["sale_price"]
        if not price:
            raise HTTPException(status_code=422, detail="Completați prețul de vânzare.")
        values.update(product_id=product["id"], product=product["name"], quantity=quantity,
                      unit_price=price, unit_cost=product["cost"], amount=round(quantity * price, 2),
                      description=body.description or f"{product['name']} ×{quantity}")
    else:
        if not body.amount:
            raise HTTPException(status_code=422, detail="Completați suma vânzării.")
        if not body.description.strip():
            raise HTTPException(status_code=422, detail="Completați descrierea.")
        values.update(product_id=None, product=None, quantity=None, unit_price=None,
                      unit_cost=body.cost_total or 0, amount=round(body.amount, 2),
                      description=body.description.strip())
    return values


SALE_COLUMNS = ["date", "description", "product", "quantity", "amount", "product_id", "client_id",
                "unit_price", "unit_cost", "due_date", "paid"]


def stock_warning(conn, product_id: int | None) -> str | None:
    if not product_id:
        return None
    product = next((p for p in inventory.products_overview(conn) if p["id"] == product_id), None)
    if product and product["stock"] < 0:
        return f"Atenție: stocul pentru „{product['name']}” a ajuns la {product['stock']} buc."
    if product and product["status"] == "low":
        return f"Mai sunt doar {product['stock']} buc. din „{product['name']}”."
    return None


@api.get("/sales")
def list_sales(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    start, end = calc.month_bounds(month)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.*, c.name AS client_name, c.type AS client_type FROM sales s "
            "LEFT JOIN clients c ON c.id = s.client_id WHERE s.date BETWEEN ? AND ? "
            "ORDER BY s.date DESC, s.id DESC",
            (start, end),
        ).fetchall()
    return [dict(row) for row in rows]


@api.get("/sales/next-invoice")
def get_next_invoice():
    with get_conn() as conn:
        return {"invoice_number": next_invoice_number(conn)}


@api.post("/sales", status_code=201)
def create_sale(body: SaleIn):
    with get_conn() as conn:
        values = sale_values(conn, body)
        values["invoice_number"] = body.invoice_number or next_invoice_number(conn)
        columns = SALE_COLUMNS + ["invoice_number"]
        cursor = conn.execute(
            f"INSERT INTO sales({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
            [values[column] for column in columns],
        )
        warning = stock_warning(conn, values["product_id"])
    return {"id": cursor.lastrowid, "invoice_number": values["invoice_number"], "warning": warning}


@api.put("/sales/{sale_id}")
def update_sale(sale_id: int, body: SaleIn):
    with get_conn() as conn:
        values = sale_values(conn, body)
        if body.invoice_number:
            values["invoice_number"] = body.invoice_number
        cursor = conn.execute(
            f"UPDATE sales SET {', '.join(f'{column} = ?' for column in values)} WHERE id = ?",
            [*values.values(), sale_id],
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Vânzarea nu există.")
        warning = stock_warning(conn, values["product_id"])
    return {"ok": True, "warning": warning}


class PaidIn(BaseModel):
    paid: bool


@api.patch("/sales/{sale_id}/paid")
def set_sale_paid(sale_id: int, body: PaidIn):
    with get_conn() as conn:
        if conn.execute("UPDATE sales SET paid = ? WHERE id = ?",
                        (int(body.paid), sale_id)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Vânzarea nu există.")
    return {"ok": True}


@api.delete("/sales/{sale_id}")
def delete_sale(sale_id: int):
    with get_conn() as conn:
        if conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Vânzarea nu există.")
    return {"ok": True}


# ---------- Cheltuieli și categorii ----------

class ExpenseIn(BaseModel):
    date: str
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=200)
    amount: float = Field(gt=0)
    supplier: str = Field(default="", max_length=120)
    vat_kind: str = Field(default="standard", pattern=VAT_KIND_PATTERN)

    @field_validator("date")
    @classmethod
    def check_date(cls, value):
        return valid_date(value)


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#94a3b8", pattern=r"^#[0-9a-fA-F]{6}$")
    vat_kind: str = Field(default="standard", pattern=VAT_KIND_PATTERN)


@api.get("/expenses")
def list_expenses(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    start, end = calc.month_bounds(month)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date DESC, id DESC",
            (start, end),
        ).fetchall()
    return [dict(row) for row in rows]


@api.post("/expenses", status_code=201)
def create_expense(body: ExpenseIn):
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO expenses(date, category, description, amount, supplier, vat_kind) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (body.date, body.category, body.description, body.amount, body.supplier, body.vat_kind),
        )
    return {"id": cursor.lastrowid}


@api.put("/expenses/{expense_id}")
def update_expense(expense_id: int, body: ExpenseIn):
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE expenses SET date = ?, category = ?, description = ?, amount = ?, supplier = ?, "
            "vat_kind = ? WHERE id = ?",
            (body.date, body.category, body.description, body.amount, body.supplier, body.vat_kind,
             expense_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Cheltuiala nu există.")
    return {"ok": True}


@api.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int):
    with get_conn() as conn:
        if conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Cheltuiala nu există.")
    return {"ok": True}


@api.get("/categories")
def list_categories():
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM categories ORDER BY name = 'Altele', id")]


@api.post("/categories", status_code=201)
def create_category(body: CategoryIn):
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM categories WHERE name = ?", (body.name,)).fetchone():
            raise HTTPException(status_code=400, detail="Categoria există deja.")
        cursor = conn.execute(
            "INSERT INTO categories(name, color, vat_kind) VALUES (?, ?, ?)",
            (body.name, body.color, body.vat_kind),
        )
    return {"id": cursor.lastrowid}


@api.delete("/categories/{category_id}")
def delete_category(category_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Categoria nu există.")
        used = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE category = ?", (row["name"],)
        ).fetchone()[0]
        if used:
            raise HTTPException(
                status_code=400,
                detail=f"Categoria are {used} cheltuieli și nu poate fi ștearsă.",
            )
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    return {"ok": True}


# ---------- Produse, stoc și recepții de marfă ----------

class ProductIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="", max_length=100)
    supplier: str = Field(default="", max_length=120)
    sale_price: float = Field(ge=0)
    cost: float = Field(ge=0)
    min_stock: int = Field(default=5, ge=0)  # pragul de alertă propus de client
    opening_stock: int = Field(default=0, ge=0)
    active: bool = True


class PurchaseIn(BaseModel):
    date: str
    product_id: int
    quantity: int = Field(ge=1)
    unit_cost: float | None = Field(default=None, gt=0)
    supplier: str = Field(default="", max_length=120)
    doc_number: str = Field(default="", max_length=40)
    paid: bool | None = None

    @field_validator("date")
    @classmethod
    def check_date(cls, value):
        return valid_date(value)


@api.get("/products")
def list_products():
    with get_conn() as conn:
        return inventory.products_overview(conn)


@api.post("/products", status_code=201)
def create_product(body: ProductIn):
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM products WHERE code = ?", (body.code,)).fetchone():
            raise HTTPException(status_code=400, detail="Există deja un produs cu acest cod.")
        supplier_terms(conn, body.supplier)
        cursor = conn.execute(
            "INSERT INTO products(code, name, category, supplier, sale_price, cost, min_stock, "
            "opening_stock, opening_date, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.code, body.name, body.category, body.supplier, body.sale_price, body.cost,
             body.min_stock, body.opening_stock, date.today().isoformat(), int(body.active)),
        )
    return {"id": cursor.lastrowid}


@api.put("/products/{product_id}")
def update_product(product_id: int, body: ProductIn):
    with get_conn() as conn:
        clash = conn.execute("SELECT id FROM products WHERE code = ? AND id != ?",
                             (body.code, product_id)).fetchone()
        if clash:
            raise HTTPException(status_code=400, detail="Există deja un produs cu acest cod.")
        cursor = conn.execute(
            "UPDATE products SET code = ?, name = ?, category = ?, supplier = ?, sale_price = ?, "
            "cost = ?, min_stock = ?, active = ? WHERE id = ?",
            (body.code, body.name, body.category, body.supplier, body.sale_price, body.cost,
             body.min_stock, int(body.active), product_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Produsul nu există.")
    return {"ok": True}


@api.delete("/products/{product_id}")
def delete_product(product_id: int):
    with get_conn() as conn:
        used = conn.execute(
            "SELECT (SELECT COUNT(*) FROM sales WHERE product_id = ?) + "
            "(SELECT COUNT(*) FROM purchases WHERE product_id = ?)", (product_id, product_id),
        ).fetchone()[0]
        if used:
            raise HTTPException(status_code=400, detail="Produsul are vânzări sau recepții. "
                                "Îl puteți marca inactiv în loc să-l ștergeți.")
        if conn.execute("DELETE FROM products WHERE id = ?", (product_id,)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Produsul nu există.")
    return {"ok": True}


@api.get("/purchases")
def list_purchases(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    start, end = calc.month_bounds(month)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT pu.*, p.name AS product_name, p.code AS product_code, "
            "pu.quantity * pu.unit_cost AS value FROM purchases pu "
            "JOIN products p ON p.id = pu.product_id WHERE pu.date BETWEEN ? AND ? "
            "ORDER BY pu.date DESC, pu.id DESC", (start, end)).fetchall()
    return [dict(row) for row in rows]


@api.post("/purchases", status_code=201)
def create_purchase(body: PurchaseIn):
    """Recepție de marfă: crește stocul. Costul intră în profit când marfa se vinde."""
    with get_conn() as conn:
        product = conn.execute("SELECT * FROM products WHERE id = ?", (body.product_id,)).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Produsul nu există.")
        cost = body.unit_cost or product["cost"]
        doc = body.doc_number or f"NIR-{date.today():%y%m%d}-{body.product_id}"
        supplier = body.supplier or product["supplier"]
        terms = supplier_terms(conn, supplier)
        due = (date.fromisoformat(body.date) + timedelta(days=terms)).isoformat()
        paid = body.paid if body.paid is not None else terms == 0
        cursor = conn.execute(
            "INSERT INTO purchases(date, doc_number, supplier, product_id, quantity, unit_cost, due_date, paid) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (body.date, doc, supplier, product["id"], body.quantity, cost, due, int(paid)),
        )
        if cost != product["cost"]:  # costul de achiziție se actualizează la ultimul preț
            conn.execute("UPDATE products SET cost = ? WHERE id = ?", (cost, product["id"]))
    return {"id": cursor.lastrowid}


@api.delete("/purchases/{purchase_id}")
def delete_purchase(purchase_id: int):
    with get_conn() as conn:
        if conn.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Recepția nu există.")
    return {"ok": True}


@api.patch("/purchases/{purchase_id}/paid")
def set_purchase_paid(purchase_id: int, body: PaidIn):
    with get_conn() as conn:
        if conn.execute("UPDATE purchases SET paid = ? WHERE id = ?",
                        (int(body.paid), purchase_id)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Recepția nu există.")
    return {"ok": True}


# ---------- Furnizori și plăți ----------

def supplier_terms(conn, name: str) -> int:
    """Termenul de plată al furnizorului; un furnizor nou primește termenul implicit."""
    if not name:
        return 0
    row = conn.execute("SELECT payment_terms FROM suppliers WHERE name = ?", (name,)).fetchone()
    if row:
        return row["payment_terms"]
    conn.execute("INSERT INTO suppliers(name, payment_terms) VALUES (?, ?)", (name, DEFAULT_SUPPLIER_TERMS))
    return DEFAULT_SUPPLIER_TERMS


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    payment_terms: int = Field(default=DEFAULT_SUPPLIER_TERMS, ge=0, le=365)
    contact: str = Field(default="", max_length=200)


@api.get("/suppliers")
def list_suppliers(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    start, end = calc.month_bounds(month)
    with get_conn() as conn:
        due = {item["supplier"]: item for item in calc.payables(conn)["suppliers"]}
        rows = conn.execute(
            "SELECT s.*, "
            "COALESCE((SELECT SUM(quantity * unit_cost) FROM purchases pu WHERE pu.supplier = s.name "
            "AND pu.date BETWEEN ? AND ?), 0) AS month_purchases, "
            "COALESCE((SELECT SUM(quantity * unit_cost) FROM purchases pu WHERE pu.supplier = s.name), 0) "
            "AS total_purchases, "
            "(SELECT COUNT(*) FROM products p WHERE p.supplier = s.name) AS products "
            "FROM suppliers s ORDER BY total_purchases DESC, s.name", (start, end)).fetchall()
        return [{**dict(row), "payable": due.get(row["name"], {}).get("amount", 0),
                 "overdue": due.get(row["name"], {}).get("overdue", 0),
                 "due_soon": due.get(row["name"], {}).get("due_soon", 0)} for row in rows]


@api.post("/suppliers", status_code=201)
def create_supplier(body: SupplierIn):
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM suppliers WHERE name = ?", (body.name,)).fetchone():
            raise HTTPException(status_code=400, detail="Furnizorul există deja.")
        cursor = conn.execute("INSERT INTO suppliers(name, payment_terms, contact) VALUES (?, ?, ?)",
                              (body.name, body.payment_terms, body.contact))
    return {"id": cursor.lastrowid}


@api.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, body: SupplierIn):
    with get_conn() as conn:
        old = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="Furnizorul nu există.")
        conn.execute("UPDATE suppliers SET name = ?, payment_terms = ?, contact = ? WHERE id = ?",
                     (body.name, body.payment_terms, body.contact, supplier_id))
        if old["name"] != body.name:  # redenumirea se vede peste tot
            for table in ("purchases", "products", "expenses"):
                conn.execute(f"UPDATE {table} SET supplier = ? WHERE supplier = ?", (body.name, old["name"]))
        if old["payment_terms"] != body.payment_terms:  # recepțiile neplătite primesc noul termen
            conn.execute("UPDATE purchases SET due_date = date(date, ?) WHERE supplier = ? AND paid = 0",
                         (f"+{body.payment_terms} days", body.name))
    return {"ok": True}


@api.get("/payables")
def get_payables():
    with get_conn() as conn:
        return calc.payables(conn)


@api.get("/inventory")
def get_inventory(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    with get_conn() as conn:
        return inventory.inventory_month(conn, month)


# ---------- Clienți și încasări ----------

class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str = Field(default="B2B", max_length=40)
    city: str = Field(default="", max_length=80)
    agent: str = Field(default="", max_length=80)
    payment_terms: int = Field(default=0, ge=0, le=365)


@api.get("/clients")
def list_clients(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    start, end = calc.month_bounds(month)
    with get_conn() as conn:
        due = {item["client"]: item for item in calc.receivables(conn)["clients"]}
        rows = conn.execute(
            "SELECT c.*, "
            "COALESCE((SELECT SUM(amount) FROM sales s WHERE s.client_id = c.id "
            "AND s.date BETWEEN ? AND ?), 0) AS month_sales, "
            "COALESCE((SELECT SUM(amount) FROM sales s WHERE s.client_id = c.id), 0) AS total_sales, "
            "(SELECT COUNT(*) FROM sales s WHERE s.client_id = c.id) AS invoices, "
            "(SELECT MAX(date) FROM sales s WHERE s.client_id = c.id) AS last_sale "
            "FROM clients c ORDER BY total_sales DESC", (start, end)).fetchall()
        return [{**dict(row), "receivable": due.get(row["name"], {}).get("amount", 0),
                 "overdue": due.get(row["name"], {}).get("overdue", 0)} for row in rows]


@api.post("/clients", status_code=201)
def create_client(body: ClientIn):
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM clients WHERE name = ?", (body.name,)).fetchone():
            raise HTTPException(status_code=400, detail="Clientul există deja.")
        cursor = conn.execute(
            "INSERT INTO clients(name, type, city, agent, payment_terms) VALUES (?, ?, ?, ?, ?)",
            (body.name, body.type, body.city, body.agent, body.payment_terms))
    return {"id": cursor.lastrowid}


@api.put("/clients/{client_id}")
def update_client(client_id: int, body: ClientIn):
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE clients SET name = ?, type = ?, city = ?, agent = ?, payment_terms = ? WHERE id = ?",
            (body.name, body.type, body.city, body.agent, body.payment_terms, client_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Clientul nu există.")
    return {"ok": True}


@api.delete("/clients/{client_id}")
def delete_client(client_id: int):
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM sales WHERE client_id = ?", (client_id,)).fetchone():
            raise HTTPException(status_code=400, detail="Clientul are facturi și nu poate fi șters.")
        if conn.execute("DELETE FROM clients WHERE id = ?", (client_id,)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Clientul nu există.")
    return {"ok": True}


@api.get("/receivables")
def get_receivables():
    with get_conn() as conn:
        return calc.receivables(conn)


# ---------- Import din fișierele firmei ----------

@api.post("/import")
async def import_data(files: list[UploadFile] = File(...), replace: bool = Form(False)):
    contents = []
    for upload in files:
        data = await upload.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"„{upload.filename}” depășește 10 MB.")
        contents.append((upload.filename or "fisier", data))
    try:
        with get_conn() as conn:
            return importer.import_files(conn, contents, replace=replace)
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=400, detail=f"Importul nu a reușit: {error}")


# ---------- Angajați și salarii ----------

class EmployeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=120)
    hire_date: str
    end_date: str | None = None
    notes: str = Field(default="", max_length=500)

    @field_validator("hire_date", "end_date")
    @classmethod
    def check_dates(cls, value):
        return valid_date(value)


class NewEmployeeIn(EmployeeIn):
    gross: float = Field(gt=0)


class SalaryIn(BaseModel):
    gross: float = Field(gt=0)
    effective_from: str
    note: str = Field(default="", max_length=200)

    @field_validator("effective_from")
    @classmethod
    def check_date(cls, value):
        return valid_date(value)


def employee_details(conn, employee) -> dict:
    settings = fiscal.settings_for_month(conn, calc.current_month())
    history = [dict(row) for row in conn.execute(
        "SELECT * FROM salary_history WHERE employee_id = ? ORDER BY effective_from DESC, id DESC",
        (employee["id"],),
    )]
    gross = calc.gross_for_month(conn, employee, calc.current_month())
    current = history[0]["gross"] if history else 0
    return {
        **dict(employee),
        "active": gross is not None,
        "salary": calc.salary_breakdown(gross if gross is not None else current, settings),
        "history": history,
    }


@api.get("/employees")
def list_employees():
    with get_conn() as conn:
        employees = conn.execute(
            "SELECT * FROM employees ORDER BY end_date IS NOT NULL, name"
        ).fetchall()
        return [employee_details(conn, employee) for employee in employees]


@api.post("/employees", status_code=201)
def create_employee(body: NewEmployeeIn):
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO employees(name, role, hire_date, end_date, notes) VALUES (?, ?, ?, ?, ?)",
            (body.name, body.role, body.hire_date, body.end_date, body.notes),
        )
        conn.execute(
            "INSERT INTO salary_history(employee_id, gross, effective_from, note) "
            "VALUES (?, ?, ?, 'Salariu inițial')",
            (cursor.lastrowid, body.gross, body.hire_date),
        )
    return {"id": cursor.lastrowid}


@api.put("/employees/{employee_id}")
def update_employee(employee_id: int, body: EmployeeIn):
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE employees SET name = ?, role = ?, hire_date = ?, end_date = ?, notes = ? "
            "WHERE id = ?",
            (body.name, body.role, body.hire_date, body.end_date, body.notes, employee_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Angajatul nu există.")
    return {"ok": True}


@api.delete("/employees/{employee_id}")
def delete_employee(employee_id: int):
    with get_conn() as conn:
        if conn.execute("DELETE FROM employees WHERE id = ?", (employee_id,)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Angajatul nu există.")
    return {"ok": True}


@api.post("/employees/{employee_id}/salary", status_code=201)
def add_salary(employee_id: int, body: SalaryIn):
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM employees WHERE id = ?", (employee_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Angajatul nu există.")
        conn.execute(
            "INSERT INTO salary_history(employee_id, gross, effective_from, note) "
            "VALUES (?, ?, ?, ?)",
            (employee_id, body.gross, body.effective_from, body.note or "Modificare salariu"),
        )
    return {"ok": True}


@api.get("/salary-preview")
def salary_preview(gross: float = Query(gt=0)):
    with get_conn() as conn:
        return calc.salary_breakdown(gross, fiscal.settings_for_month(conn, calc.current_month()))


# ---------- Setări ----------

class SettingsIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    owner_name: str = Field(default="", max_length=60)
    tax_regime: str = Field(pattern="^(profit|micro)$")
    vat_payer: bool = True


@api.get("/settings")
def read_settings():
    with get_conn() as conn:
        settings = get_settings(conn)
    return {key: settings.get(key, default) for key, default in DEFAULT_SETTINGS.items()}


@api.put("/settings")
def write_settings(body: SettingsIn):
    with get_conn() as conn:
        for key, value in body.model_dump().items():
            set_setting(conn, key, ("1" if value else "0") if isinstance(value, bool) else str(value))
    return {"ok": True}


# ---------- Legislație fiscală ----------

@api.get("/fiscal")
def fiscal_overview():
    with get_conn() as conn:
        return fiscal.overview(conn)


@api.post("/fiscal/check")
async def fiscal_check():
    return await asyncio.to_thread(run_fiscal_check)


@api.post("/fiscal/seen")
def fiscal_seen():
    with get_conn() as conn:
        fiscal.mark_seen(conn)
    return {"ok": True}


# ---------- Asistentul AI (opțional) ----------

class AISettingsIn(BaseModel):
    enabled: bool
    api_key: str | None = Field(default=None, max_length=300)
    clear_key: bool = False


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


@api.get("/ai/status")
def ai_status():
    with get_conn() as conn:
        return assistant_ai.status(conn)


@api.put("/ai/settings")
def ai_settings(body: AISettingsIn):
    with get_conn() as conn:
        assistant_ai.save_settings(conn, body.enabled, body.api_key, body.clear_key)
        return assistant_ai.status(conn)


@api.post("/ai/chat")
def ai_chat(body: ChatIn):
    try:
        with get_conn() as conn:
            return assistant_ai.ask(conn, [m.model_dump() for m in body.messages])
    except assistant_ai.AIError as error:
        raise HTTPException(status_code=error.status, detail=str(error))


@api.post("/demo")
def reload_demo():
    with get_conn() as conn:
        return demo.load_demo_data(conn)


app.include_router(api)
