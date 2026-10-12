"""Categorisire: cache pe disc -> un apel AI batch -> reguli (doar ca rezervă)."""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from . import ai

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "categorii_cache.json"
_lock = threading.Lock()

# Rezervă când AI-ul nu e disponibil (fără cheie / fără rețea). Ordinea contează:
# „BOLT FOOD” trebuie prins înainte de „BOLT”.
RULES: list[tuple[str, str]] = [
    (r"bolt food|glovo|tazz|foodpanda|restaurant|bistro|pizza|starbucks|cafe|coffee|mcdonald|kfc", "Mâncare"),
    (r"mega image|lidl|kaufland|carrefour|auchan|profi|penny|alimentar|supermarket|la doi pasi", "Mâncare"),
    (r"bolt|uber|taxi|omv|petrom|mol |rompetrol|lukoil|benzin|rca|asigurari auto|parcare|metrorex|stb", "Transport"),
    (r"enel|engie|e\.on|eon |electrica|apa nova|digi|rcs|orange|vodafone|telekom|internet|gaz", "Utilități"),
    (r"chirie|intretinere|întreținere|administrator bloc", "Locuință"),
    (r"farmaci|catena|dr\.? max|sensiblu|help net|clinic|regina maria|medlife|paracetamol", "Sănătate"),
    (r"netflix|spotify|hbo|disney|cinema|steam|playstation|youtube|teatru|concert", "Divertisment"),
    (r"booking|airbnb|hotel|wizz|ryanair|tarom|blue air|aeroport", "Călătorii"),
    (r"emag|altex|decathlon|zara|h&m|ikea|dedeman|amazon|fashion|mall", "Shopping"),
    (r"salariu|dobanda|dobândă|transfer primit|incasare|încasare", "Venituri"),
    (r"comision", "Altele"),
]


def normalize_key(desc: str) -> str:
    """„MEGA IMAGE 0123 BUCURESTI” și „MEGA IMAGE 0456 BUCURESTI” -> aceeași cheie."""
    s = desc.upper()
    s = re.sub(r"^(PLATA CARD|PLATA|DEBIT DIRECT|POS)\s+", "", s)
    s = re.sub(r"\d+", " ", s)
    s = re.sub(r"[^\wĂÂÎȘŞȚŢ&.]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def rule_category(desc: str) -> str | None:
    low = desc.lower()
    for pattern, cat in RULES:
        if re.search(pattern, low):
            return cat
    return None


def _load() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def remember(desc: str, category: str) -> None:
    """Corecțiile manuale din UI ajung în cache: data viitoare nu mai întrebăm AI-ul."""
    with _lock:
        cache = _load()
        cache[normalize_key(desc)] = category
        _save(cache)


def categorize(txs: list[dict]) -> dict:
    """Completează tx['category'] și tx['category_by']. Întoarce statistici."""
    stats = {"cache": 0, "ai": 0, "reguli": 0, "ai_error": None}
    with _lock:
        cache = _load()

    pending: dict[str, tuple[str, str]] = {}
    for tx in txs:
        if tx.get("category") in ai.CATEGORII:  # ex. bon extras deja de AI
            tx.setdefault("category_by", "AI")
            continue
        if tx["direction"] == "credit":
            # Încasările nu sunt cheltuieli: le marcăm direct, fără AI.
            tx["category"], tx["category_by"] = "Venituri", "regulă: încasare"
            continue
        key = normalize_key(tx["description"])
        if key in cache:
            tx["category"], tx["category_by"] = cache[key], "AI (din cache)"
            stats["cache"] += 1
        else:
            pending.setdefault(key, (tx["description"], tx["direction"]))

    ai_result: dict[str, str] = {}
    if pending and ai.enabled():
        keys = list(pending)
        try:
            res = ai.categorize_batch([pending[k] for k in keys])
            ai_result = {keys[i]: cat for i, cat in res.items() if 0 <= i < len(keys)}
            with _lock:
                cache = _load()
                cache.update(ai_result)
                _save(cache)
        except ai.AIUnavailable as e:
            stats["ai_error"] = str(e)
    elif pending:
        stats["ai_error"] = "AI dezactivat (lipsește ANTHROPIC_API_KEY) – am folosit reguli locale."

    for tx in txs:
        if tx.get("category"):
            continue
        key = normalize_key(tx["description"])
        if key in ai_result:
            tx["category"], tx["category_by"] = ai_result[key], "AI"
            stats["ai"] += 1
        else:
            tx["category"] = rule_category(tx["description"]) or "Altele"
            if tx["category"] == "Venituri":  # un debit nu poate fi venit
                tx["category"] = "Altele"
            tx["category_by"] = "reguli locale"
            stats["reguli"] += 1
    return stats
