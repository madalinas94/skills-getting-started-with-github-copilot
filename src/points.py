"""
Credite și puncte bonus pentru studenți.

Punctele NU se salvează ca număr: se calculează mereu din ce a făcut
studentul (teme, idei, voturi) plus bonusurile date de trainer. Așa nu pot
fi „umflate” din browser și se corectează singure dacă trainerul schimbă
ceva (de exemplu anulează „Aleasă”).
"""

from collections import defaultdict

RULES = {
    "submission": 10,       # temă sau proiect predat
    "on_time": 5,           # predat înainte de termenul temei
    "reviewed": 20,         # trainerul a marcat „revizuit ✓” (sau punctele temei, dacă are)
    "idea": 5,              # idee pusă în cutie
    "vote": 2,              # fiecare vot primit de la colegi
    "chosen": 30,           # idee aleasă de trainer
    "question": 2,          # întrebare pusă (maxim QUESTIONS_PER_DAY pe zi)
}
QUESTIONS_PER_DAY = 3

LEVELS = [  # (puncte minime, cheie de traducere)
    (0, "rookie"), (50, "apprentice"), (120, "crafter"),
    (220, "builder"), (350, "shipper"), (520, "wizard"),
]


def level_for(total: int) -> dict:
    current, nxt = LEVELS[0], None
    for i, lvl in enumerate(LEVELS):
        if total >= lvl[0]:
            current = lvl
            nxt = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    return {
        "index": LEVELS.index(current) + 1,
        "key": current[1],
        "min": current[0],
        "next_min": nxt[0] if nxt else None,
        "next_key": nxt[1] if nxt else None,
    }


def compute(db: dict) -> dict:
    """Întoarce {student_key: {"total", "events": [...]}} pentru toți studenții."""
    out = defaultdict(lambda: {"total": 0, "events": []})
    assignments = {a["id"]: a for a in db.get("assignments", [])}

    def add(key, kind, pts, ref=None, at=None):
        if pts:
            out[key]["total"] += pts
            out[key]["events"].append({"kind": kind, "points": pts, "ref": ref, "at": at})

    # Teme & proiecte: o singură predare punctată per temă anunțată
    counted_assignments = set()
    for sub in sorted(db.get("submissions", []), key=lambda x: x["created_at"]):
        if sub["kind"] == "other":
            continue
        key, aid = sub["author_key"], sub.get("assignment_id")
        if aid is not None:
            if (key, aid) in counted_assignments:
                continue
            counted_assignments.add((key, aid))
        add(key, "submission", RULES["submission"], sub["title"], sub["created_at"])
        a = assignments.get(aid)
        if a and a.get("due_at") and sub["created_at"] <= a["due_at"]:
            add(key, "on_time", RULES["on_time"], sub["title"], sub["created_at"])
        if sub.get("status") == "reviewed":
            pts = a.get("points", RULES["reviewed"]) if a else RULES["reviewed"]
            add(key, "reviewed", pts, sub["title"], sub.get("reviewed_at"))

    for p in db.get("proposals", []):
        key = p["author_key"]
        add(key, "idea", RULES["idea"], p["title"], p["created_at"])
        add(key, "vote", RULES["vote"] * len([v for v in p["voters"] if v != key]), p["title"], p["created_at"])
        if p.get("chosen"):
            add(key, "chosen", RULES["chosen"], p["title"], p["created_at"])

    per_day = defaultdict(int)
    for q in db.get("questions", []):
        day = (q["author_key"], q["created_at"][:10])
        per_day[day] += 1
        if per_day[day] <= QUESTIONS_PER_DAY:
            add(q["author_key"], "question", RULES["question"], q["text"][:60], q["created_at"])

    for b in db.get("bonuses", []):
        add(b["student_key"], "bonus", b["points"], b["reason"], b["created_at"])

    return out


def badges(key: str, db: dict, total: int) -> list:
    subs = [x for x in db.get("submissions", []) if x["author_key"] == key and x["kind"] != "other"]
    ideas = [p for p in db.get("proposals", []) if p["author_key"] == key]
    votes = sum(len([v for v in p["voters"] if v != key]) for p in ideas)
    questions = [q for q in db.get("questions", []) if q["author_key"] == key]
    checks = {
        "first_question": len(questions) >= 1,
        "first_homework": len(subs) >= 1,
        "five_homework": len(subs) >= 5,
        "first_idea": len(ideas) >= 1,
        "crowd_favorite": votes >= 5,
        "chosen": any(p.get("chosen") for p in ideas),
        "perfectionist": any(x.get("status") == "reviewed" and len(x.get("checklist", [])) == 6 for x in subs),
        "century": total >= 100,
    }
    return [k for k, ok in checks.items() if ok]
