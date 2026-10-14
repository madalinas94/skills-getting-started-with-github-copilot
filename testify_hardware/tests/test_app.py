import os
import tempfile
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import calc
from app.db import DEFAULT_SETTINGS


@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("TESTIFY_DB", os.path.join(tmp, "test.db"))
        from app.main import app
        with TestClient(app) as test_client:
            test_client.post("/api/auth/setup", json={"password": "parola123"})
            yield test_client


def test_salary_breakdown_from_gross():
    result = calc.salary_breakdown(5000, DEFAULT_SETTINGS)
    assert result["cas"] == 1250
    assert result["cass"] == 500
    assert result["income_tax"] == 325
    assert result["net"] == 2925
    assert result["cam"] == 112.5
    assert result["employer_cost"] == 5112.5


def test_api_requires_login(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("TESTIFY_DB", os.path.join(tmp, "test.db"))
        from app.main import app
        with TestClient(app) as anonymous:
            assert anonymous.get("/api/dashboard").status_code == 401
            anonymous.post("/api/auth/setup", json={"password": "parola123"})
            anonymous.cookies.clear()
            assert anonymous.post("/api/auth/login", json={"password": "gresit"}).status_code == 401
            assert anonymous.post("/api/auth/login", json={"password": "parola123"}).status_code == 200
            assert anonymous.get("/api/dashboard").status_code == 200


def test_setup_only_once(client):
    response = client.post("/api/auth/setup", json={"password": "altaparola"})
    assert response.status_code == 400


def test_monthly_summary_combines_sales_expenses_salaries_and_taxes(client):
    client.post("/api/sales", json={"date": "2026-03-10", "description": "Comandă mouse",
                                    "product": "Mouse", "quantity": 2, "amount": 6000})
    client.post("/api/sales", json={"date": "2026-03-11", "description": "Total zi",
                                    "amount": 4000})
    client.post("/api/expenses", json={"date": "2026-03-05", "category": "Chirie",
                                       "amount": 2000})
    client.post("/api/employees", json={"name": "Ana Pop", "role": "Vânzări",
                                        "hire_date": "2026-01-01", "gross": 5000})

    summary = client.get("/api/summary?month=2026-03").json()
    assert summary["revenue"] == 10000
    assert summary["operating_expenses"] == 2000
    assert summary["payroll"]["gross"] == 5000
    assert summary["taxes"]["micro_tax"] == 100
    # 2000 cheltuieli + 5112,5 cost salariu + 100 impozit micro
    assert summary["total_costs"] == 7212.5
    assert summary["profit"] == 2787.5
    assert summary["dividend_tax"] == 446.0
    assert summary["owner_income"] == 2341.5


def test_salary_change_applies_from_its_date(client):
    employee_id = client.post("/api/employees", json={
        "name": "Ion Rus", "hire_date": "2026-01-15", "gross": 4000}).json()["id"]
    client.post(f"/api/employees/{employee_id}/salary",
                json={"gross": 4800, "effective_from": "2026-04-01"})

    assert client.get("/api/payroll?month=2025-12").json()["lines"] == []
    assert client.get("/api/payroll?month=2026-03").json()["totals"]["gross"] == 4000
    assert client.get("/api/payroll?month=2026-04").json()["totals"]["gross"] == 4800


def test_employee_with_end_date_leaves_payroll(client):
    employee_id = client.post("/api/employees", json={
        "name": "Dan Gol", "hire_date": "2026-01-01", "gross": 4000}).json()["id"]
    client.put(f"/api/employees/{employee_id}", json={
        "name": "Dan Gol", "hire_date": "2026-01-01", "end_date": "2026-02-20"})

    assert client.get("/api/payroll?month=2026-02").json()["totals"]["gross"] == 4000
    assert client.get("/api/payroll?month=2026-03").json()["lines"] == []


def test_invalid_input_is_rejected(client):
    bad_date = client.post("/api/sales", json={"date": "10.03.2026", "description": "x", "amount": 5})
    negative = client.post("/api/sales", json={"date": "2026-03-10", "description": "x", "amount": -5})
    bad_month = client.get("/api/dashboard?month=2026-13")
    assert bad_date.status_code == negative.status_code == bad_month.status_code == 422


def test_category_in_use_cannot_be_deleted(client):
    categories = client.get("/api/categories").json()
    rent = next(c for c in categories if c["name"] == "Chirie")
    client.post("/api/expenses", json={"date": "2026-03-05", "category": "Chirie", "amount": 100})
    assert client.delete(f"/api/categories/{rent['id']}").status_code == 400


def test_settings_change_tax_rates(client):
    settings = client.get("/api/settings").json()
    settings["micro_tax_rate"] = 3
    assert client.put("/api/settings", json=settings).status_code == 200
    client.post("/api/sales", json={"date": "2026-03-10", "description": "x", "amount": 1000})
    assert client.get("/api/summary?month=2026-03").json()["taxes"]["micro_tax"] == 30


def test_demo_data_dashboard_and_exports(client):
    assert client.post("/api/demo").status_code == 200
    month = calc.shift_month(date.today().strftime("%Y-%m"), -1)
    dashboard = client.get(f"/api/dashboard?month={month}").json()
    assert dashboard["current"]["revenue"] > 0
    assert len(dashboard["trend"]) == 12
    assert dashboard["flow"] and dashboard["insights"]
    assert len(client.get("/api/employees").json()) == 6

    excel = client.get(f"/api/export/excel?month={month}")
    assert excel.status_code == 200 and excel.content[:2] == b"PK"
    pdf = client.get(f"/api/export/pdf?month={month}")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
