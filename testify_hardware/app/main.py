"""Testify Hardware — aplicația internă pentru calculul lunar.

Pornire: uvicorn app.main:app --host 0.0.0.0 --port 8000 (din folderul testify_hardware)
"""

import asyncio
import re
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import auth, calc, demo, exports, fiscal
from .db import DEFAULT_SETTINGS, get_conn, get_settings, init_db, set_setting

STATIC_DIR = Path(__file__).resolve().parent / "static"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


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
        }


@app.post("/api/auth/setup")
def auth_setup(body: SetupIn, response: Response):
    with get_conn() as conn:
        if auth.is_setup_done(conn):
            raise HTTPException(status_code=400, detail="Parola a fost deja setată.")
        auth.set_password(conn, body.password)
        if body.demo:
            demo.load_demo_data(conn)
        start_session(response, conn)
    return {"ok": True}


@app.post("/api/auth/login")
def auth_login(body: PasswordIn, response: Response):
    with get_conn() as conn:
        if not auth.check_password(conn, body.password):
            raise HTTPException(status_code=401, detail="Parolă greșită.")
        start_session(response, conn)
    return {"ok": True}


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
    date: str
    description: str = Field(min_length=1, max_length=200)
    product: str | None = Field(default=None, max_length=200)
    quantity: int | None = Field(default=None, ge=1)
    amount: float = Field(gt=0)

    @field_validator("date")
    @classmethod
    def check_date(cls, value):
        return valid_date(value)


@api.get("/sales")
def list_sales(month: str = Query(default_factory=calc.current_month, pattern=MONTH_PATTERN)):
    start, end = calc.month_bounds(month)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sales WHERE date BETWEEN ? AND ? ORDER BY date DESC, id DESC",
            (start, end),
        ).fetchall()
    return [dict(row) for row in rows]


@api.post("/sales", status_code=201)
def create_sale(body: SaleIn):
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO sales(date, description, product, quantity, amount) VALUES (?, ?, ?, ?, ?)",
            (body.date, body.description, body.product or None, body.quantity, body.amount),
        )
    return {"id": cursor.lastrowid}


@api.put("/sales/{sale_id}")
def update_sale(sale_id: int, body: SaleIn):
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE sales SET date = ?, description = ?, product = ?, quantity = ?, amount = ? "
            "WHERE id = ?",
            (body.date, body.description, body.product or None, body.quantity, body.amount, sale_id),
        )
        if cursor.rowcount == 0:
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

    @field_validator("date")
    @classmethod
    def check_date(cls, value):
        return valid_date(value)


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#94a3b8", pattern=r"^#[0-9a-fA-F]{6}$")


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
            "INSERT INTO expenses(date, category, description, amount) VALUES (?, ?, ?, ?)",
            (body.date, body.category, body.description, body.amount),
        )
    return {"id": cursor.lastrowid}


@api.put("/expenses/{expense_id}")
def update_expense(expense_id: int, body: ExpenseIn):
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE expenses SET date = ?, category = ?, description = ?, amount = ? WHERE id = ?",
            (body.date, body.category, body.description, body.amount, expense_id),
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
            "INSERT INTO categories(name, color) VALUES (?, ?)", (body.name, body.color)
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


@api.get("/settings")
def read_settings():
    with get_conn() as conn:
        settings = get_settings(conn)
    return {key: settings.get(key, default) for key, default in DEFAULT_SETTINGS.items()}


@api.put("/settings")
def write_settings(body: SettingsIn):
    with get_conn() as conn:
        for key, value in body.model_dump().items():
            set_setting(conn, key, str(value))
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


@api.post("/demo")
def reload_demo():
    with get_conn() as conn:
        demo.load_demo_data(conn)
    return {"ok": True}


app.include_router(api)
