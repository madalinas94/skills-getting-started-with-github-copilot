"""Testi cu inteligență artificială (opțional): răspunde la întrebări despre cifrele firmei.

Funcționează doar dacă proprietarul activează opțiunea și pune o cheie API Anthropic.
La fiecare întrebare, aplicația trimite modelului Claude un rezumat al datelor firmei
(luni, stoc, clienți, furnizori, salarii) și conversația de până atunci. Fără cheie,
aplicația rămâne complet locală, iar Testi folosește doar regulile lui obișnuite.
"""

import json
import os
import sqlite3
from datetime import date

import anthropic

from . import calc, inventory
from .db import get_settings, set_setting
from .fiscal import settings_for_month

AI_MODEL = "claude-opus-5-5"
MAX_TURNS = 12  # câte mesaje din conversație se trimit (ultimele)

SYSTEM_PROMPT = """Ești Testi, asistentul financiar din aplicația internă a unei firme mici din România \
care vinde accesorii IT. Vorbești cu proprietarul firmei: un antreprenor, nu un contabil, care vrea \
răspunsuri clare și scurte.

Cum răspunzi:
- În limba română, cu diacritice, pe un ton prietenos, la persoana a doua singular („ai încasat”).
- Pe baza datelor firmei din mesajul de sistem (JSON). Nu inventa cifre. Dacă o informație nu e în \
date, spune asta și ce ar trebui introdus în aplicație ca să poți răspunde.
- Cu cifre concrete: sume în lei (format românesc, de exemplu 12.345 lei), luni numite explicit.
- Scurt: 2–6 propoziții sau o listă scurtă. Fără tabele mari. Poți folosi **îngroșat** și liste cu „- ”.
- Când explici o schimbare (de exemplu de ce a scăzut profitul), compară lunile și numește cauzele \
din date: vânzări, costul mărfii, cheltuieli pe categorii, salarii, impozit.
- Pentru decizii fiscale sau juridice, dă orientarea din date, dar recomandă confirmarea cu contabilul.

Termeni din date: revenue = venituri fără TVA; cogs = costul mărfii vândute; gross_margin = marja brută; \
opex_total = cheltuieli operaționale inclusiv salarii brute și CAM; profit = profit net după impozitul \
pe profit; owner_income = ce rămâne proprietarului după impozitul pe dividende; receivables = bani de \
încasat de la clienți (cu TVA); payables = bani de plătit furnizorilor (cu TVA); days_left = în câte \
zile se termină stocul la ritmul actual de vânzare."""


class AIError(Exception):
    """Eroare explicată pe înțeles, afișată direct proprietarului."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def stored_key(conn: sqlite3.Connection) -> str:
    return get_settings(conn).get("anthropic_api_key", "")


def status(conn: sqlite3.Connection) -> dict:
    settings = get_settings(conn)
    key = settings.get("anthropic_api_key", "")
    env_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_key = bool(key) or env_key
    return {
        "enabled": settings.get("ai_enabled") == "1" and has_key,
        "switched_on": settings.get("ai_enabled") == "1",
        "has_key": has_key,
        "key_source": "setări" if key else ("variabilă de mediu" if env_key else None),
        "key_hint": f"{key[:7]}…{key[-4:]}" if len(key) > 12 else None,
        "model": AI_MODEL,
    }


def save_settings(conn: sqlite3.Connection, enabled: bool, api_key: str | None, clear_key: bool) -> None:
    set_setting(conn, "ai_enabled", "1" if enabled else "0")
    if clear_key:
        set_setting(conn, "anthropic_api_key", "")
    elif api_key:
        set_setting(conn, "anthropic_api_key", api_key.strip())


def business_snapshot(conn: sqlite3.Connection, today: str | None = None) -> dict:
    """Rezumatul datelor firmei pe care îl primește modelul (fără parole sau alte setări)."""
    today = today or date.today().isoformat()
    settings = settings_for_month(conn, today[:7])
    first = calc.first_data_month(conn) or today[:7]
    months, ym = [], today[:7]
    while ym >= first and len(months) < 12:
        s = calc.month_summary(conn, ym)
        months.append({
            "month": ym, "label": s["label"], "in_progress": ym == today[:7],
            "revenue": s["revenue"], "invoices": s["sales_count"], "cogs": s["cogs"],
            "gross_margin": s["gross_margin"], "gross_margin_pct": s["gross_margin_pct"],
            "expenses_by_category": s["expenses_by_category"], "salaries_gross": s["payroll"]["gross"],
            "salaries_net": s["payroll"]["net"], "opex_total": s["opex_total"],
            "profit_before_tax": s["profit_before_tax"], "company_tax": s["taxes"]["company_tax"],
            "profit": s["profit"], "owner_income": s["owner_income"],
            "vat_payable": s["vat"]["payable"] if s["vat"] else None,
            "purchases": s["purchases"], "stock_value": s["stock_value"],
        })
        ym = calc.shift_month(ym, -1)
    months.reverse()

    receivables = calc.receivables(conn, today)
    payables = calc.payables(conn, today)
    products = inventory.products_overview(conn, today)
    clients = [dict(row) for row in conn.execute(
        "SELECT c.name, c.type, c.city, c.agent, c.payment_terms, "
        "COALESCE(SUM(s.amount), 0) AS total_sales, COUNT(s.id) AS invoices, MAX(s.date) AS last_sale "
        "FROM clients c LEFT JOIN sales s ON s.client_id = c.id GROUP BY c.id ORDER BY total_sales DESC")]
    employees = calc.payroll(conn, today[:7])["lines"]
    return {
        "company": settings.get("company_name"),
        "today": today,
        "tax_regime": settings.get("tax_regime"),
        "vat_payer": settings.get("vat_payer", "1") == "1",
        "tax_rates_percent": {key: settings[key] for key in (
            "cas_rate", "cass_rate", "income_tax_rate", "cam_rate", "profit_tax_rate",
            "micro_tax_rate", "dividend_tax_rate", "vat_standard_rate", "vat_reduced_rate")},
        "months": months,
        "receivables": {"total": receivables["total"], "overdue": receivables["overdue"],
                        "by_client": receivables["clients"]},
        "payables": {"total": payables["total"], "overdue": payables["overdue"],
                     "due_next_7_days": payables["due_soon"], "by_supplier": payables["suppliers"]},
        "products": [{key: p[key] for key in ("code", "name", "category", "supplier", "sale_price", "cost",
                                              "margin_pct", "stock", "min_stock", "status", "stock_value",
                                              "sold_30", "days_left")} for p in products if p["active"]],
        "clients": clients,
        "employees": [{key: e[key] for key in ("name", "role", "gross", "net", "employer_cost")}
                      for e in employees],
    }


def make_client(conn: sqlite3.Connection) -> anthropic.Anthropic:
    key = stored_key(conn)
    # Fără cheie salvată, SDK-ul folosește ANTHROPIC_API_KEY din mediu.
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


def clean_history(messages: list[dict]) -> list[dict]:
    """Ultimele mesaje, alternând corect și începând cu o întrebare."""
    history = [{"role": m["role"], "content": m["content"].strip()} for m in messages
               if m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip()]
    history = history[-MAX_TURNS:]
    while history and history[0]["role"] != "user":
        history.pop(0)
    if not history or history[-1]["role"] != "user":
        raise AIError("Scrieți o întrebare pentru Testi.", 400)
    return history


def ask(conn: sqlite3.Connection, messages: list[dict]) -> dict:
    if not status(conn)["enabled"]:
        raise AIError("Asistentul AI nu este activat. Îl puteți porni din Setări.", 400)
    history = clean_history(messages)
    snapshot = json.dumps(business_snapshot(conn), ensure_ascii=False, separators=(",", ":"))
    client = make_client(conn)
    try:
        response = client.beta.messages.create(
            model=AI_MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # dacă modelul refuză o întrebare, o preia automat modelul de rezervă
            output_config={"effort": "medium"},
            # Instrucțiunile fixe primele (se pot reține în cache), datele firmei după ele.
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": f"Datele firmei (JSON, sume în lei):\n{snapshot}"},
            ],
            messages=history,
        )
    except anthropic.AuthenticationError:
        raise AIError("Cheia API nu este validă. Verificați-o în Setări.", 400)
    except anthropic.PermissionDeniedError:
        raise AIError("Cheia API nu are acces la acest model.", 400)
    except anthropic.RateLimitError:
        raise AIError("Prea multe întrebări într-un timp scurt. Încercați din nou peste un minut.", 429)
    except anthropic.APIConnectionError:
        raise AIError("Nu există conexiune la internet. Testi cu AI are nevoie de internet.", 503)
    except anthropic.APIStatusError as error:
        raise AIError(f"Serviciul AI a răspuns cu o eroare ({error.status_code}). Încercați mai târziu.")

    if response.stop_reason == "refusal":
        return {"reply": "Nu pot răspunde la această întrebare. Încearcă să o formulezi altfel, "
                         "legat de cifrele firmei.", "model": response.model}
    text = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise AIError("Nu am primit un răspuns. Încercați din nou.")
    return {"reply": text, "model": response.model}
