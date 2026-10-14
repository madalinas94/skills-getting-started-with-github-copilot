"""Teste pe datele reale ale firmei: aplicația trebuie să dea aceleași cifre ca raportul contabil."""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data"

# Valorile calculate de contabil în „raport_contabil_T3_2026.xlsx” (foaia Rezumat).
ACCOUNTANT = {
    "2026-07": {"revenue": 149435.57, "cogs": 84135, "gross_margin": 65300.57, "opex_total": 49222.9,
                "profit_before_tax": 16077.67, "company_tax": 2572, "profit": 13505.67,
                "vat_payable": 8981.59, "stock_value": 43557, "purchases": 92900, "net_salaries": 20196,
                "sales_count": 119},
    "2026-08": {"revenue": 124418.19, "cogs": 69320, "gross_margin": 55098.19, "opex_total": 49965.9,
                "profit_before_tax": 5132.29, "company_tax": 821, "profit": 4311.29,
                "vat_payable": 10642.04, "stock_value": 33477, "purchases": 59240, "net_salaries": 20196,
                "sales_count": 118},
    "2026-09": {"revenue": 152654.62, "cogs": 84270, "gross_margin": 68384.62, "opex_total": 49306.95,
                "profit_before_tax": 19077.67, "company_tax": 3052, "profit": 16025.67,
                "vat_payable": 12150.3, "stock_value": 30162, "purchases": 80955, "net_salaries": 20196,
                "sales_count": 114},
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TESTIFY_FISCAL_FEED", "")
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("TESTIFY_DB", os.path.join(tmp, "test.db"))
        from app.main import app
        with TestClient(app) as test_client:
            test_client.post("/api/auth/setup", json={"password": "parola123"})
            yield test_client


def upload(client, *names, replace=False):
    files = [("files", (name, (SAMPLE / name).read_bytes())) for name in names]
    response = client.post("/api/import", files=files, data={"replace": str(replace).lower()})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("month", ACCOUNTANT)
def test_figures_match_the_accountant_report(client, month):
    client.post("/api/demo")
    summary = client.get(f"/api/summary?month={month}").json()
    expected = ACCOUNTANT[month]
    actual = {
        "revenue": summary["revenue"], "cogs": summary["cogs"], "gross_margin": summary["gross_margin"],
        "opex_total": summary["opex_total"], "profit_before_tax": summary["profit_before_tax"],
        "company_tax": summary["taxes"]["company_tax"], "profit": summary["profit"],
        "vat_payable": summary["vat"]["payable"], "stock_value": summary["stock_value"],
        "purchases": summary["purchases"], "net_salaries": summary["payroll"]["net"],
        "sales_count": summary["sales_count"],
    }
    assert actual == pytest.approx(expected, abs=0.01)


def test_receivables_match_the_accountant_report(client):
    from app import calc
    from app.db import get_conn

    client.post("/api/demo")
    with get_conn() as conn:
        assert calc.receivables(conn, "2026-09-30")["total"] == pytest.approx(141646.71, abs=0.01)


def test_september_csv_files_alone_give_the_same_september(client):
    result = upload(client, "produse.csv", "clienti.csv", "angajati.csv", "inventar_septembrie_2026.csv",
                    "vanzari_septembrie_2026.csv", "cheltuieli_septembrie_2026.csv")
    assert result["counts"]["sales"] == 114
    summary = client.get("/api/summary?month=2026-09").json()
    expected = ACCOUNTANT["2026-09"]
    assert summary["revenue"] == pytest.approx(expected["revenue"])
    assert summary["cogs"] == pytest.approx(expected["cogs"])
    assert summary["opex_total"] == pytest.approx(expected["opex_total"])
    assert summary["profit"] == pytest.approx(expected["profit"])
    assert summary["stock_value"] == pytest.approx(expected["stock_value"])
    inventory = client.get("/api/inventory?month=2026-09").json()
    hub = next(line for line in inventory["lines"] if line["code"] == "P101")
    assert (hub["initial"], hub["entries"], hub["exits"], hub["final"]) == (10, 20, 25, 5)


def test_importing_the_same_files_twice_adds_nothing(client):
    client.post("/api/demo")
    again = upload(client, "raport_contabil_T3_2026.xlsx", "vanzari_septembrie_2026.csv",
                   "cheltuieli_septembrie_2026.csv", "inventar_septembrie_2026.csv")
    assert again["counts"] == {}
    assert client.get("/api/summary?month=2026-09").json()["revenue"] == ACCOUNTANT["2026-09"]["revenue"]


def test_expense_vat_types_are_read_from_the_report(client):
    client.post("/api/demo")
    expenses = client.get("/api/expenses?month=2026-09").json()
    kinds = {x["description"]: x["vat_kind"] for x in expenses}
    assert kinds["Apa si canalizare august"] == "reduced"
    assert kinds["Comisioane bancare"] == "none"
    assert kinds["Chirie spatiu birou + depozit"] == "standard"
    assert {x["category"] for x in expenses} >= {"Utilități", "Comisioane bancare și POS"}


def test_sale_lowers_stock_and_purchase_raises_it(client):
    client.post("/api/demo")
    hub = next(p for p in client.get("/api/products").json() if p["code"] == "P101")
    assert hub["stock"] == 5 and hub["status"] == "low"

    sale = client.post("/api/sales", json={"date": "2026-10-14", "product_id": hub["id"], "quantity": 3}).json()
    assert sale["invoice_number"] == "NB-1115"
    assert "2 buc." in sale["warning"]
    assert next(p for p in client.get("/api/products").json() if p["id"] == hub["id"])["stock"] == 2

    client.post("/api/purchases", json={"date": "2026-10-14", "product_id": hub["id"], "quantity": 30})
    after = next(p for p in client.get("/api/products").json() if p["id"] == hub["id"])
    assert after["stock"] == 32 and after["status"] == "ok"


def test_sale_to_b2b_client_waits_for_payment(client):
    client.post("/api/demo")
    alfa = next(c for c in client.get("/api/clients").json() if c["name"] == "Alfa Office SRL")
    product = client.get("/api/products").json()[0]
    before = client.get("/api/receivables").json()["total"]

    sale_id = client.post("/api/sales", json={"date": "2026-10-14", "product_id": product["id"],
                                              "client_id": alfa["id"], "quantity": 1}).json()["id"]
    sale = next(s for s in client.get("/api/sales?month=2026-10").json() if s["id"] == sale_id)
    assert sale["paid"] == 0 and sale["due_date"] == "2026-11-13"   # termen de plată 30 de zile
    with_vat = round(product["sale_price"] * 1.21, 2)
    assert client.get("/api/receivables").json()["total"] == pytest.approx(before + with_vat)

    client.patch(f"/api/sales/{sale_id}/paid", json={"paid": True})
    assert client.get("/api/receivables").json()["total"] == pytest.approx(before)


def test_without_vat_setting_no_vat_is_calculated(client):
    client.post("/api/demo")
    settings = client.get("/api/settings").json()
    client.put("/api/settings", json={**settings, "vat_payer": False})
    summary = client.get("/api/summary?month=2026-09").json()
    assert summary["vat"] is None
    assert summary["profit"] == ACCOUNTANT["2026-09"]["profit"]


def test_bad_import_changes_nothing(client):
    client.post("/api/demo")
    files = [("files", ("note.txt", b"nu e tabel"))]
    assert client.post("/api/import", files=files, data={"replace": "true"}).status_code == 400
    assert client.get("/api/summary?month=2026-09").json()["sales_count"] == 114
