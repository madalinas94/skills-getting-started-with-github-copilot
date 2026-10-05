"""
Cutia Clasei

Aplicație FastAPI în care studenții pun întrebări trainerului și propun
proiecte pentru ora următoare. Propunerile trec printr-un modul AI care le
retușează și cere detalii doar unde lipsesc; studentul aprobă varianta finală
înainte să o trimită. Trainerul răspunde la întrebări și marchează propunerile
alese.
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

current_dir = Path(__file__).parent


def load_env_file(path: Path):
    """Citește KEY=VALUE din .env (fișier ignorat de git). Variabilele deja
    setate în mediu au prioritate. Cheia API rămâne doar pe server."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(current_dir.parent / ".env")

try:
    from . import ai
except ImportError:  # rulare directă: python app.py
    import ai

DATA_FILE = Path(os.environ.get("CUTIA_DATA", current_dir.parent / "data" / "cutia.json"))
TRAINER_CODE = os.environ.get("TRAINER_CODE", "trainer")

app = FastAPI(title="Cutia Clasei API",
              description="Întrebări pentru trainer și propuneri de proiecte")

app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")

# ---------------------------------------------------------------------------
# Stocare: în memorie, salvată într-un fișier JSON ca să supraviețuiască
# repornirilor. Sesiunile (token -> utilizator) stau doar în memorie.
# ---------------------------------------------------------------------------

_lock = threading.Lock()
db = {"users": {}, "questions": [], "proposals": [], "next_id": 1}
sessions: dict[str, dict] = {}


def load_db():
    if DATA_FILE.exists():
        try:
            db.update(json.loads(DATA_FILE.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass


def save_db():
    if os.environ.get("CUTIA_PERSIST", "1") == "0":
        return
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def next_id() -> int:
    value = db["next_id"]
    db["next_id"] += 1
    return value


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


load_db()

# ---------------------------------------------------------------------------
# Autentificare: studentul are cont cu nume + parolă (creat la prima intrare),
# trainerul intră cu codul din TRAINER_CODE.
# ---------------------------------------------------------------------------


class LoginIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    role: str = Field(pattern="^(student|trainer)$")
    password: Optional[str] = Field(None, max_length=200)
    code: Optional[str] = None


def hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def check_student(name: str, password: str):
    """Creează contul la prima intrare; după aceea cere aceeași parolă."""
    if len(password or "") < 4:
        raise HTTPException(status_code=400, detail="Parola trebuie să aibă minim 4 caractere.")
    key = name.casefold()
    with _lock:
        user = db["users"].get(key)
        if user is None:
            salt = secrets.token_bytes(16)
            db["users"][key] = {"name": name, "salt": salt.hex(),
                                "hash": hash_password(password, salt)}
            save_db()
            return
    expected = hash_password(password, bytes.fromhex(user["salt"]))
    if not hmac.compare_digest(expected, user["hash"]):
        raise HTTPException(status_code=401,
                            detail="Parolă greșită. Numele e deja folosit de alt cont.")


def current_user(authorization: Optional[str] = Header(None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = sessions.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Autentifică-te din nou.")
    return user


def require_trainer(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "trainer":
        raise HTTPException(status_code=403, detail="Doar trainerul poate face asta.")
    return user


def require_student(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Doar studenții pot face asta.")
    return user


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.post("/api/login")
def login(body: LoginIn):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Scrie-ți numele.")
    if body.role == "trainer":
        if not hmac.compare_digest((body.code or "").encode(), TRAINER_CODE.encode()):
            raise HTTPException(status_code=403, detail="Cod de trainer greșit.")
    else:
        check_student(name, body.password)
    token = secrets.token_urlsafe(24)
    sessions[token] = {"name": name, "role": body.role, "key": name.casefold()}
    return {"token": token, "name": name, "role": body.role}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return {"name": user["name"], "role": user["role"]}


# ---------------------------------------------------------------------------
# Întrebări: le vede doar autorul și trainerul.
# ---------------------------------------------------------------------------

CATEGORIES = ["General", "Teorie", "Cod", "Temă", "Altceva"]


class QuestionIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    category: str = "General"
    anonymous: bool = False


class AnswerIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def question_view(q: dict, user: dict) -> dict:
    view = {k: v for k, v in q.items() if k != "author_key"}
    view["mine"] = q["author_key"] == user["key"]
    if user["role"] == "trainer" and q["anonymous"]:
        view["author"] = "Anonim"
    return view


@app.get("/api/categories")
def categories():
    return CATEGORIES


@app.get("/api/questions")
def list_questions(user: dict = Depends(current_user)):
    items = db["questions"]
    if user["role"] != "trainer":
        items = [q for q in items if q["author_key"] == user["key"]]
    return [question_view(q, user) for q in reversed(items)]


@app.post("/api/questions", status_code=201)
def ask_question(body: QuestionIn, user: dict = Depends(require_student)):
    text = body.text.strip()
    if len(text) < 3:
        raise HTTPException(status_code=400, detail="Întrebarea e prea scurtă.")
    with _lock:
        q = {
            "id": next_id(),
            "text": text,
            "category": body.category if body.category in CATEGORIES else "General",
            "anonymous": body.anonymous,
            "author": user["name"],
            "author_key": user["key"],
            "created_at": now(),
            "answer": None,
            "answered_at": None,
        }
        db["questions"].append(q)
        save_db()
    return question_view(q, user)


@app.post("/api/questions/{question_id}/answer")
def answer_question(question_id: int, body: AnswerIn, user: dict = Depends(require_trainer)):
    with _lock:
        q = next((q for q in db["questions"] if q["id"] == question_id), None)
        if not q:
            raise HTTPException(status_code=404, detail="Întrebarea nu există.")
        q["answer"] = body.text.strip()
        q["answered_at"] = now()
        save_db()
    return question_view(q, user)


# ---------------------------------------------------------------------------
# Propuneri: AI-ul retușează, studentul aprobă, apoi trimite.
# Toată clasa vede propunerile trimise și poate vota; trainerul le alege.
# ---------------------------------------------------------------------------


class ProposalDraft(BaseModel):
    title: str = Field("", max_length=200)
    description: str = Field("", max_length=4000)
    audience: str = Field("", max_length=500)


class ProposalIn(ProposalDraft):
    approved: bool = False


def proposal_view(p: dict, user: dict) -> dict:
    view = {k: v for k, v in p.items() if k not in ("author_key", "voters")}
    view["votes"] = len(p["voters"])
    view["voted"] = user["key"] in p["voters"]
    view["mine"] = p["author_key"] == user["key"]
    return view


@app.post("/api/proposals/refine")
def refine_proposal(body: ProposalDraft, user: dict = Depends(require_student)):
    if not (body.title.strip() or body.description.strip() or body.audience.strip()):
        raise HTTPException(status_code=400, detail="Scrie măcar o idee înainte de retușare.")
    return ai.refine(body.title, body.description, body.audience)


@app.post("/api/proposals", status_code=201)
def submit_proposal(body: ProposalIn, user: dict = Depends(require_student)):
    if not body.approved:
        raise HTTPException(status_code=400, detail="Aprobă varianta finală înainte să o trimiți.")
    fields = {k: getattr(body, k).strip() for k in ("title", "description", "audience")}
    empty = [ai.FIELDS[k] for k, v in fields.items() if not v]
    if empty:
        raise HTTPException(status_code=400, detail="Lipsește: " + ", ".join(empty) + ".")
    with _lock:
        p = {
            "id": next_id(),
            **fields,
            "author": user["name"],
            "author_key": user["key"],
            "created_at": now(),
            "chosen": False,
            "voters": [],
        }
        db["proposals"].append(p)
        save_db()
    return proposal_view(p, user)


@app.get("/api/proposals")
def list_proposals(user: dict = Depends(current_user)):
    return [proposal_view(p, user) for p in reversed(db["proposals"])]


def find_proposal(proposal_id: int) -> dict:
    p = next((p for p in db["proposals"] if p["id"] == proposal_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="Propunerea nu există.")
    return p


@app.post("/api/proposals/{proposal_id}/vote")
def toggle_vote(proposal_id: int, user: dict = Depends(require_student)):
    with _lock:
        p = find_proposal(proposal_id)
        if user["key"] in p["voters"]:
            p["voters"].remove(user["key"])
        else:
            p["voters"].append(user["key"])
        save_db()
    return proposal_view(p, user)


@app.post("/api/proposals/{proposal_id}/choose")
def toggle_chosen(proposal_id: int, user: dict = Depends(require_trainer)):
    with _lock:
        p = find_proposal(proposal_id)
        p["chosen"] = not p["chosen"]
        save_db()
    return proposal_view(p, user)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
