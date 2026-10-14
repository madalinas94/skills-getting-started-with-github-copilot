import json
import os
import tempfile
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import calc, fiscal

RATES_2026 = {"cas_rate": 25, "cass_rate": 10, "income_tax_rate": 10, "cam_rate": 2.25}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    # Testele nu descarcă regulile fiscale de pe internet.
    monkeypatch.setenv("TESTIFY_FISCAL_FEED", "")


@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("TESTIFY_DB", os.path.join(tmp, "test.db"))
        from app.main import app
        with TestClient(app) as test_client:
            test_client.post("/api/auth/setup", json={"password": "parola123"})
            yield test_client


def test_salary_breakdown_from_gross():
    result = calc.salary_breakdown(5000, RATES_2026)
    assert result["cas"] == 1250
    assert result["cass"] == 500
    assert result["income_tax"] == 325
    assert result["net"] == 2925
    # Contribuțiile se rotunjesc la leu, cu 0,5 în sus (112,5 → 113), ca în statul de plată.
    assert result["cam"] == 113
    assert result["employer_cost"] == 5113


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


def add_product(client, **overrides):
    body = {"code": "T1", "name": "Mouse test", "sale_price": 100, "cost": 60,
            "min_stock": 5, "opening_stock": 20, **overrides}
    return client.post("/api/products", json=body).json()["id"]


def test_monthly_summary_follows_the_accountant_model(client):
    product = add_product(client)
    client.post("/api/sales", json={"date": "2026-03-10", "product_id": product, "quantity": 20,
                                    "unit_price": 300})
    client.post("/api/sales", json={"date": "2026-03-11", "description": "Total zi",
                                    "amount": 4000, "cost_total": 1000})
    client.post("/api/expenses", json={"date": "2026-03-05", "category": "Chirie",
                                       "amount": 1000})
    client.post("/api/employees", json={"name": "Ana Pop", "role": "Vânzări",
                                        "hire_date": "2026-01-01", "gross": 5000})

    summary = client.get("/api/summary?month=2026-03").json()
    assert summary["revenue"] == 10000
    # costul mărfii vândute: 20 × 60 din stoc + 1000 la vânzarea totală
    assert summary["cogs"] == 2200
    assert summary["gross_margin"] == 7800
    assert summary["opex_total"] == 6113          # 1000 cheltuieli + 5000 brut + 113 CAM
    assert summary["profit_before_tax"] == 1687
    assert summary["taxes"]["company_tax"] == 270  # 16% din 1687 = 269,92 → 270
    assert summary["profit"] == 1417
    assert summary["dividend_tax"] == 226.72
    assert summary["owner_income"] == 1190.28
    # TVA: 21% din vânzări − 21% din chirie
    assert summary["vat"] == {"collected": 2100, "deductible_purchases": 0, "deductible_expenses": 210,
                              "deductible": 210, "payable": 1890}


def test_no_profit_tax_in_a_loss_month(client):
    client.post("/api/sales", json={"date": "2026-03-10", "description": "x", "amount": 1000})
    client.post("/api/expenses", json={"date": "2026-03-05", "category": "Chirie", "amount": 3000})
    summary = client.get("/api/summary?month=2026-03").json()
    assert summary["taxes"]["company_tax"] == 0
    assert summary["profit"] == -2000


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


def test_settings_switch_to_micro_regime(client):
    settings = client.get("/api/settings").json()
    assert settings["owner_name"] == "Robert"
    settings["tax_regime"] = "micro"
    assert client.put("/api/settings", json=settings).status_code == 200
    client.post("/api/sales", json={"date": "2026-03-10", "description": "x", "amount": 1000})
    summary = client.get("/api/summary?month=2026-03").json()
    assert summary["taxes"]["company_tax"] == 10
    assert summary["company_tax_label"] == "Impozit microîntreprindere"


def test_each_month_uses_the_tax_rules_valid_then(client):
    for day in ("2025-12-10", "2026-01-10"):
        client.post("/api/sales", json={"date": day, "description": "x", "amount": 10000})
    december = client.get("/api/summary?month=2025-12").json()
    january = client.get("/api/summary?month=2026-01").json()
    assert december["rates"]["dividend_tax_rate"] == 10
    assert january["rates"]["dividend_tax_rate"] == 16
    # 10000 profit înainte de impozit → 8400 după impozitul pe profit de 16%
    assert december["dividend_tax"] == 840
    assert january["dividend_tax"] == 1344


def bundled_rules():
    return json.loads(fiscal.BUNDLED_RULES.read_text(encoding="utf-8"))["rules"]


def write_feed(folder, rules):
    path = os.path.join(folder, "feed.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"version": "2027.1", "source": "test", "rules": rules}, handle)
    return "file://" + path


def test_automatic_update_adds_new_rule_and_notifies(client):
    from app.db import get_conn

    new_rule = {
        "effective_from": "2099-01-01",
        "title": "Modificări de test",
        "rates": {**bundled_rules()[-1]["rates"], "profit_tax_rate": 20},
        "changes": ["Impozitul pe profit crește la 20%."],
    }
    with tempfile.TemporaryDirectory() as tmp, get_conn() as conn:
        url = write_feed(tmp, [new_rule])
        result = fiscal.check_for_updates(conn, url)
        assert result["ok"] and result["changed"] == ["2099-01-01"]
        # A doua verificare nu mai găsește nimic nou.
        assert fiscal.check_for_updates(conn, url)["changed"] == []

    overview = client.get("/api/fiscal").json()
    assert overview["version"] == "2027.1"
    assert [rule["effective_from"] for rule in overview["unseen"]] == ["2099-01-01"]
    assert overview["upcoming"][0]["rates"]["profit_tax_rate"] == 20
    assert overview["current"]["rates"]["profit_tax_rate"] == 16

    client.post("/api/fiscal/seen")
    assert client.get("/api/fiscal").json()["unseen"] == []


def test_invalid_or_unreachable_feed_keeps_existing_rules(client):
    from app.db import get_conn

    with tempfile.TemporaryDirectory() as tmp, get_conn() as conn:
        bad = write_feed(tmp, [{"effective_from": "2099-01-01", "rates": {"cas_rate": 500}}])
        assert fiscal.check_for_updates(conn, bad)["ok"] is False
        missing = "file://" + os.path.join(tmp, "nu-exista.json")
        assert fiscal.check_for_updates(conn, missing)["ok"] is False
    overview = client.get("/api/fiscal").json()
    assert overview["last_status"] == "error"
    assert all(rule["effective_from"] < "2099-01-01" for rule in overview["history"])


def test_demo_data_dashboard_and_exports(client):
    assert client.post("/api/demo").status_code == 200
    month = "2026-09"
    dashboard = client.get(f"/api/dashboard?month={month}").json()
    assert dashboard["current"]["revenue"] > 0
    # Evoluția pornește de la prima lună cu date (iulie 2026).
    assert [m["month"] for m in dashboard["trend"]] == ["2026-07", "2026-08", "2026-09"]
    assert dashboard["flow"] and dashboard["insights"]
    assert len(client.get("/api/employees").json()) == 6

    excel = client.get(f"/api/export/excel?month={month}")
    assert excel.status_code == 200 and excel.content[:2] == b"PK"
    pdf = client.get(f"/api/export/pdf?month={month}")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_default_categories_cover_common_expenses(client):
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert len(names) == 19
    assert {"Software și abonamente", "Comisioane bancare și POS", "Asigurări"} <= set(names)
    assert names[-1] == "Altele"


def test_small_categories_are_grouped_in_money_flow(client):
    for index, category in enumerate(c["name"] for c in client.get("/api/categories").json()):
        client.post("/api/expenses", json={"date": "2026-03-05", "category": category,
                                           "amount": 100 + index})
    flow = client.get("/api/dashboard?month=2026-03").json()["flow"]
    assert len(flow) == calc.FLOW_MAX_ITEMS
    grouped = flow[-1]
    assert grouped["name"] == "Alte 11 categorii"
    assert grouped["amount"] == sum(item["amount"] for item in grouped["details"])
