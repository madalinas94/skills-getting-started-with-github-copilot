"""Teste fără AI (rulează fără cheie API): parsare, deduplicare, totaluri, întrebări."""
import os
from pathlib import Path

import pytest

os.environ.pop("ANTHROPIC_API_KEY", None)  # testele trebuie să fie deterministe și gratuite

from fastapi.testclient import TestClient  # noqa: E402

from backend import categorize as cat_mod  # noqa: E402
from backend import main  # noqa: E402
from backend.parsers import parse_amount, parse_date  # noqa: E402
from backend.store import Store  # noqa: E402

FILES = Path(__file__).resolve().parent.parent / "fisiere-test"


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend import ai
    monkeypatch.setattr(ai, "enabled", lambda: False)  # testele nu folosesc niciodată cheia din .env
    monkeypatch.setattr(main, "store", Store(tmp_path / "tx.json"))
    monkeypatch.setattr(cat_mod, "CACHE_FILE", tmp_path / "cache.json")
    main._q_cache.clear()
    return TestClient(main.app)


def upload(client, *names):
    files = [("files", (n, (FILES / n).read_bytes())) for n in names]
    return client.post("/api/upload", files=files).json()


def add_receipts(client):
    # bonurile foto au nevoie de AI; în teste le introducem manual, ca în UI
    client.post("/api/transactions", json={"date": "14/03/2026", "description": "MAGAZIN ALIMENTAR DEMO SRL",
                                           "amount": "73,50", "category": "Mâncare"})
    client.post("/api/transactions", json={"date": "21.03.2026", "description": "FARMACIA DEMO",
                                           "amount": "38,90", "category": "Sănătate"})


def ask(client, q, cur="RON"):
    return client.post("/api/ask", json={"question": q, "display_currency": cur}).json()


@pytest.mark.parametrize("text,expected", [
    ("2026-02-27", "2026-02-27"), ("01/03/2026", "2026-03-01"), ("2.03.2026", "2026-03-02"),
    ("3 mar. 2026", "2026-03-03"), ("12 mar. 2026", "2026-03-12"), ("1 apr. 2026", "2026-04-01"),
])
def test_dates(text, expected):
    assert parse_date(text).isoformat() == expected


@pytest.mark.parametrize("text,expected", [
    ("1.249,99", 1249.99), ("87,45", 87.45), ("6.500,00", 6500.0), ("0,42", 0.42),
    ("1,249.99", 1249.99), ("-59,99", -59.99), ("280.00", 280.0), ("", None),
])
def test_amounts(text, expected):
    assert parse_amount(text) == expected


def test_csv_upload(client):
    r = upload(client, "tranzactii_card.csv")
    assert r["reports"][0]["added"] == 24  # „Total inregistrari: 24” confirmă
    txs = r["transactions"]
    transfer = next(t for t in txs if "TRANSFER PRIMIT" in t["description"])
    assert transfer["direction"] == "credit" and transfer["category"] == "Venituri"
    booking = next(t for t in txs if "BOOKING" in t["description"])
    assert booking["currency"] == "EUR" and booking["amount"] == 145.0


def test_same_file_twice_is_ignored(client):
    upload(client, "tranzactii_card.csv")
    r = upload(client, "tranzactii_card.csv")
    assert r["reports"][0]["added"] == 0 and "deja" in r["reports"][0]["error"]
    assert len(r["transactions"]) == 24


def test_pdf_dedup_with_csv(client):
    r = upload(client, "tranzactii_card.csv", "extras_cont_martie_2026.pdf")
    pdf = [t for t in r["transactions"] if t["source"] == "extras_pdf"]
    assert len(pdf) == 9  # fără rândurile „Sold inițial/final”
    dups = sorted(t["amount"] for t in pdf if t["duplicate_of"])
    assert dups == [214.37, 312.80, 1249.99]  # Kaufland, eMAG, Enel apar în ambele surse


def test_food_march_csv_only(client):
    upload(client, "tranzactii_card.csv")
    r = ask(client, "Cât am cheltuit pe mâncare în martie?")
    # 245.30+312.80+78.40+24.00+56.75+92.15+198.60+136.50+41.20 (fără 27 feb și 1 apr)
    assert r["total"] == 1185.70
    assert r["count"] == 9


def test_all_sources_totals(client):
    upload(client, "tranzactii_card.csv", "extras_cont_martie_2026.pdf")
    add_receipts(client)
    food = ask(client, "Cât am cheltuit pe mâncare în martie?")
    assert food["total"] == round(1185.70 + 73.50, 2)

    total = ask(client, "Cât am cheltuit în martie?")
    csv_march_ron = (245.30 + 23.50 + 59.99 + 312.80 + 78.40 + 280.00 + 1249.99 + 29.99 + 64.20 + 24.00
                     + 56.75 + 52.00 + 92.15 + 31.40 + 198.60 + 349.00 + 214.37 + 136.50 + 250.00 + 41.20)
    pdf_unique = 2200.00 + 55.00 + 9.00 + 620.00
    expected = csv_march_ron + 145.00 * 5.25 + pdf_unique + 73.50 + 38.90
    assert total["total"] == round(expected, 2)

    income = ask(client, "Cât am încasat în martie?")
    assert income["total"] == round(6500.00 + 200.00 + 0.42, 2)


def test_currency_conversion_and_filter(client):
    upload(client, "tranzactii_card.csv")
    eur = ask(client, "Cât am cheltuit pe mâncare în martie?", cur="EUR")
    assert eur["currency"] == "EUR" and eur["total"] == round(1185.70 / 5.25, 2)
    usd = ask(client, "Cât am cheltuit pe mâncare în martie?", cur="USD")
    assert usd["total"] == round(1185.70 / 4.40, 2)
    only_eur = ask(client, "Câte tranzacții am făcut în euro?")
    assert only_eur["count"] == 1


def test_cash_question(client):
    upload(client, "tranzactii_card.csv")
    add_receipts(client)
    r = ask(client, "Cât am plătit cash?")
    assert r["total"] == round(73.50 + 38.90, 2)


def test_category_correction_is_remembered(client):
    r = upload(client, "tranzactii_card.csv")
    tx = next(t for t in r["transactions"] if "DECATHLON" in t["description"])
    client.patch(f"/api/transactions/{tx['id']}", json={"category": "Divertisment"})
    assert cat_mod._load()[cat_mod.normalize_key("DECATHLON BANEASA")] == "Divertisment"


def test_ai_path_with_mocked_claude(client, monkeypatch):
    """Ramura AI, cu răspunsurile lui Claude simulate: verifică cablajul, nu modelul."""
    from backend import ai
    calls = []

    def fake_call(system, content, schema, max_tokens=0):
        calls.append(schema)
        if schema is ai._CAT_SCHEMA:
            import json as _j
            items = _j.loads(content.split("\n", 1)[1])
            return {"rezultate": [{"id": it["id"], "categorie": cat_mod.rule_category(it["descriere"]) or "Altele"}
                                  for it in items]}
        if schema is ai._DOC_SCHEMA:
            return {"tranzactii": [{"data": "2026-03-14", "descriere": "MAGAZIN ALIMENTAR DEMO SRL", "suma": 73.5,
                                    "moneda": "RON", "directie": "debit", "categorie": "Mâncare", "metoda_plata": "numerar"}]}
        return {"operatie": "suma", "tip": "cheltuieli", "categorii": ["Mâncare"], "luna": "2026-03", "data_de_la": "",
                "data_pana_la": "", "text_cautat": "", "surse": [], "moneda_originala": "", "moneda_afisare": "",
                "limita": 0, "interpretare": "mâncare în martie 2026", "in_afara_domeniului": False}

    monkeypatch.setattr(ai, "enabled", lambda: True)
    monkeypatch.setattr(ai, "_call_json", fake_call)

    r = upload(client, "tranzactii_card.csv", "bon_alimentara.jpg")
    assert r["reports"][0]["categorii"]["ai"] > 0
    assert len([c for c in calls if c is ai._CAT_SCHEMA]) == 1  # un singur apel batch pentru tot CSV-ul
    assert r["reports"][1]["added"] == 1

    a1 = ask(client, "Cât am cheltuit pe mâncare în martie?")
    a2 = ask(client, "Cât am cheltuit pe mâncare în martie?")
    assert a1["mode"] == "AI" and a2["mode"] == "cache"
    assert a1["total"] == round(1185.70 + 73.50, 2)

    # re-upload după reset: categoriile vin din cache, zero apeluri noi
    client.delete("/api/transactions")
    n = len(calls)
    upload(client, "tranzactii_card.csv")
    assert len(calls) == n


def test_insights(client):
    upload(client, "tranzactii_card.csv", "extras_cont_martie_2026.pdf")
    add_receipts(client)
    ins = client.get("/api/insights", params={"month": "2026-03", "currency": "RON"}).json()
    assert ins["totals"]["income"] == 6700.42
    assert ins["totals"]["net"] < 0
    assert ins["alerts"][0]["level"] == "danger"  # a cheltuit mai mult decât a încasat
    ids = {r["id"] for r in ins["recommendations"]}
    assert {"food", "subs", "fees", "shopping", "transport", "save"} <= ids
    assert ins["potential_saving"] > 0 and 0 < ins["score"] <= 100
    assert sum(r["total"] for r in ins["categories"]) == pytest.approx(ins["totals"]["expenses"], abs=0.05)
    eur = client.get("/api/insights", params={"month": "2026-03", "currency": "EUR"}).json()
    assert eur["totals"]["expenses"] == pytest.approx(ins["totals"]["expenses"] / 5.25, abs=0.01)


def test_demo_endpoint(client):
    r = client.post("/api/demo").json()
    names = {x["file"] for x in r["reports"]}
    assert "tranzactii_card.csv" in names and "extras_cont_martie_2026.pdf" in names


def test_insights_empty(client):
    ins = client.get("/api/insights").json()
    assert ins["categories"] == [] and ins["recommendations"] == []
    upload(client, "extras_cont_martie_2026.pdf")  # doar extras: fără Mâncare
    assert client.get("/api/insights", params={"month": "2026-03"}).status_code == 200


def test_english(client):
    upload(client, "tranzactii_card.csv", "extras_cont_martie_2026.pdf")
    r = client.post("/api/ask", json={"question": "How much did I spend on food in March?", "lang": "en"}).json()
    assert r["total"] == 1185.70 and r["answer"].startswith("You spent") and "Food" in r["answer"]
    ins = client.get("/api/insights", params={"month": "2026-03", "lang": "en"}).json()
    assert ins["alerts"][0]["title"] == "You spent more than you earned"
    assert ins["personality"]["title"].startswith("The ")
    assert all(c["label"] in ("Housing", "Shopping", "Transport", "Food", "Travel", "Utilities",
                              "Entertainment", "Health", "Other") for c in ins["categories"])
    ro = client.get("/api/insights", params={"month": "2026-03", "lang": "ro"}).json()
    assert ro["totals"] == ins["totals"]  # limba schimbă doar textele, nu cifrele


def test_pwa_files(client):
    assert client.get("/manifest.webmanifest").json()["short_name"] == "Finn"
    assert "service" in client.get("/sw.js").text.lower()


def test_owner_from_statement(client):
    r = upload(client, "extras_cont_martie_2026.pdf")
    assert r["owner"] == "Matei Ionescu"
    assert client.get("/api/transactions").json()["owner"] == "Matei Ionescu"


def test_budgets(client):
    upload(client, "tranzactii_card.csv", "extras_cont_martie_2026.pdf")
    sug = client.get("/api/budgets", params={"month": "2026-03"}).json()["suggested"]
    assert sug["Locuință"] == 2000.0  # 30% din 6.700,42, rotunjit la 50
    ins = client.get("/api/insights", params={"month": "2026-03"}).json()["budgets"]
    assert ins["counts"]["unset"] == 9 and not ins["has_any"]

    client.put("/api/budgets", json={"budgets": {"Mâncare": 1000, "Utilități": 400, "Shopping": 0}})
    b = client.get("/api/insights", params={"month": "2026-03"}).json()["budgets"]
    by = {x["category"]: x for x in b["items"]}
    assert by["Mâncare"]["status"] == "over" and by["Mâncare"]["diff"] == 185.70
    assert by["Utilități"]["status"] == "ok" and by["Utilități"]["diff"] == round(400 - 269.37, 2)
    assert by["Shopping"]["status"] == "unset"
    assert b["counts"] == {"over": 1, "ok": 1, "unset": 7}
    assert b["items"][0]["category"] == "Mâncare"  # depășirile apar primele

    # bugetele se pot trimite și în EUR; se stochează în RON
    client.put("/api/budgets", json={"budgets": {"Mâncare": 200}, "currency": "EUR"})
    assert client.get("/api/budgets").json()["budgets"]["Mâncare"] == 1050.0
