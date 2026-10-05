"""
Cutia Clasei · platforma internă a cursului de vibe coding.

Spațiul privat (student ↔ trainer): mesaje directe, întrebări, teme & proiecte.
Spațiul public (toată clasa): cutia de idei, AI News, ghidul, clasamentul.
Toate regulile de acces se verifică aici, pe server.
"""

import contextvars
import hashlib
import hmac
import json
import os
import secrets
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
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
    from . import ai, news, points
except ImportError:  # rulare directă: python app.py
    import ai
    import news
    import points

DATA_FILE = Path(os.environ.get("CUTIA_DATA", current_dir.parent / "data" / "cutia.json"))
UPLOAD_DIR = Path(os.environ.get("CUTIA_UPLOADS", DATA_FILE.parent / "uploads"))
TRAINER_CODE = os.environ.get("TRAINER_CODE", "trainer")

app = FastAPI(title="Cutia Clasei API",
              description="Întrebări pentru trainer și propuneri de proiecte")

# ---------------------------------------------------------------------------
# Limba: interfața trimite antetul X-Lang (ro, en, fr, it, es, de); mesajele
# de eroare și textele AI vin în limba aleasă.
# ---------------------------------------------------------------------------

current_lang = contextvars.ContextVar("current_lang", default="ro")

# Ordinea traducerilor: ro, en, fr, it, es, de (ca în ai.LANGS)
MESSAGES = {
    "short_password": ("Parola trebuie să aibă minim 8 caractere.", "Password must be at least 8 characters.", "Le mot de passe doit avoir au moins 8 caractères.", "La password deve avere almeno 8 caratteri.", "La contraseña debe tener al menos 8 caracteres.", "Das Passwort muss mindestens 8 Zeichen haben."),
    "bad_email": ("Adresa de email nu pare corectă.", "That email address doesn't look right.", "Cette adresse e-mail ne semble pas correcte.", "Questo indirizzo email non sembra corretto.", "Ese correo no parece correcto.", "Diese E-Mail-Adresse sieht nicht richtig aus."),
    "email_taken": ("Există deja un cont cu acest email. Intră în cont.", "An account with this email already exists. Sign in instead.", "Un compte existe déjà avec cet e-mail. Connecte-toi.", "Esiste già un account con questa email. Accedi.", "Ya existe una cuenta con este correo. Inicia sesión.", "Mit dieser E-Mail gibt es schon ein Konto. Melde dich an."),
    "wrong_login": ("Email sau parolă greșită.", "Wrong email or password.", "E-mail ou mot de passe incorrect.", "Email o password errati.", "Correo o contraseña incorrectos.", "E-Mail oder Passwort falsch."),
    "too_many_attempts": ("Prea multe încercări. Mai încearcă peste 10 minute.", "Too many attempts. Try again in 10 minutes.", "Trop de tentatives. Réessaie dans 10 minutes.", "Troppi tentativi. Riprova tra 10 minuti.", "Demasiados intentos. Vuelve a intentarlo en 10 minutos.", "Zu viele Versuche. Versuch es in 10 Minuten wieder."),
    "wrong_class_code": ("Codul clasei nu e corect. Îl primești de la trainer.", "The class code isn't right. Ask the trainer for it.", "Le code de la classe n'est pas correct. Demande-le au formateur.", "Il codice della classe non è corretto. Chiedilo al trainer.", "El código de la clase no es correcto. Pídeselo al formador.", "Der Klassencode stimmt nicht. Frag den Trainer danach."),
    "wrong_current": ("Parola actuală nu e corectă.", "Your current password isn't right.", "Le mot de passe actuel n'est pas correct.", "La password attuale non è corretta.", "La contraseña actual no es correcta.", "Das aktuelle Passwort stimmt nicht."),
    "google_off": ("Intrarea cu Google nu e configurată pe server.", "Google sign-in isn't configured on the server.", "La connexion Google n'est pas configurée sur le serveur.", "L'accesso con Google non è configurato sul server.", "El inicio de sesión con Google no está configurado en el servidor.", "Die Google-Anmeldung ist auf dem Server nicht eingerichtet."),
    "google_failed": ("Nu am putut verifica contul Google. Încearcă din nou.", "Couldn't verify the Google account. Try again.", "Impossible de vérifier le compte Google. Réessaie.", "Impossibile verificare l'account Google. Riprova.", "No se pudo verificar la cuenta de Google. Inténtalo de nuevo.", "Das Google-Konto konnte nicht geprüft werden. Versuch es nochmal."),
    "login_again": ("Autentifică-te din nou.", "Please sign in again.", "Reconnecte-toi.", "Accedi di nuovo.", "Vuelve a iniciar sesión.", "Bitte melde dich erneut an."),
    "trainer_only": ("Doar trainerul poate face asta.", "Only the trainer can do this.", "Seul le formateur peut faire ça.", "Solo il trainer può farlo.", "Solo el formador puede hacer esto.", "Nur der Trainer kann das tun."),
    "student_only": ("Doar studenții pot face asta.", "Only students can do this.", "Seuls les étudiants peuvent faire ça.", "Solo gli studenti possono farlo.", "Solo los estudiantes pueden hacer esto.", "Nur Studierende können das tun."),
    "need_name": ("Scrie-ți numele.", "Enter your name.", "Écris ton nom.", "Scrivi il tuo nome.", "Escribe tu nombre.", "Gib deinen Namen ein."),
    "wrong_code": ("Cod de trainer greșit.", "Wrong trainer code.", "Code formateur incorrect.", "Codice trainer errato.", "Código de formador incorrecto.", "Falscher Trainer-Code."),
    "too_short": ("Textul e prea scurt.", "The text is too short.", "Le texte est trop court.", "Il testo è troppo corto.", "El texto es demasiado corto.", "Der Text ist zu kurz."),
    "no_question": ("Întrebarea nu există.", "Question not found.", "Question introuvable.", "Domanda non trovata.", "Pregunta no encontrada.", "Frage nicht gefunden."),
    "not_yours": ("Poți cere răspuns AI doar pentru întrebările tale.", "You can only ask the AI about your own questions.", "Tu ne peux demander l'IA que pour tes propres questions.", "Puoi chiedere all'IA solo sulle tue domande.", "Solo puedes pedir a la IA sobre tus propias preguntas.", "Du kannst die KI nur zu deinen eigenen Fragen fragen."),
    "ai_off": ("AI-ul nu e configurat pe server (lipsește cheia API).", "AI is not configured on the server (missing API key).", "L'IA n'est pas configurée sur le serveur (clé API manquante).", "L'IA non è configurata sul server (manca la chiave API).", "La IA no está configurada en el servidor (falta la clave API).", "Die KI ist auf dem Server nicht eingerichtet (API-Schlüssel fehlt)."),
    "ai_failed": ("AI-ul nu a putut răspunde acum. Încearcă din nou.", "The AI couldn't answer right now. Try again.", "L'IA n'a pas pu répondre. Réessaie.", "L'IA non ha potuto rispondere. Riprova.", "La IA no pudo responder. Inténtalo de nuevo.", "Die KI konnte gerade nicht antworten. Versuch es nochmal."),
    "empty_idea": ("Scrie măcar o idee înainte de retușare.", "Write at least an idea before the AI touch-up.", "Écris au moins une idée avant la retouche IA.", "Scrivi almeno un'idea prima del ritocco IA.", "Escribe al menos una idea antes del retoque IA.", "Schreib zuerst eine Idee, bevor die KI sie überarbeitet."),
    "approve_first": ("Aprobă varianta finală înainte să o trimiți.", "Approve the final version before submitting it.", "Approuve la version finale avant de l'envoyer.", "Approva la versione finale prima di inviarla.", "Aprueba la versión final antes de enviarla.", "Bestätige die finale Version, bevor du sie sendest."),
    "missing": ("Lipsește: {}.", "Missing: {}.", "Il manque : {}.", "Manca: {}.", "Falta: {}.", "Es fehlt: {}."),
    "no_proposal": ("Propunerea nu există.", "Proposal not found.", "Proposition introuvable.", "Proposta non trovata.", "Propuesta no encontrada.", "Vorschlag nicht gefunden."),
    "withdrawn": ("Propunerea a fost retrasă de autor.", "The author withdrew this proposal.", "L'auteur a retiré cette proposition.", "L'autore ha ritirato questa proposta.", "El autor retiró esta propuesta.", "Der Vorschlag wurde vom Autor zurückgezogen."),
    "not_author": ("Doar autorul poate face asta.", "Only the author can do this.", "Seul l'auteur peut faire ça.", "Solo l'autore può farlo.", "Solo el autor puede hacer esto.", "Nur der Autor kann das tun."),
    "too_many_drafts": ("Poți păstra maxim {} ciorne. Șterge una veche.", "You can keep at most {} drafts. Delete an old one.", "Tu peux garder au maximum {} brouillons. Supprimes-en un ancien.", "Puoi tenere al massimo {} bozze. Eliminane una vecchia.", "Puedes guardar como máximo {} borradores. Borra uno antiguo.", "Du kannst höchstens {} Entwürfe behalten. Lösch einen alten."),
    "no_draft": ("Ciorna nu există.", "Draft not found.", "Brouillon introuvable.", "Bozza non trovata.", "Borrador no encontrado.", "Entwurf nicht gefunden."),
    "own_vote": ("Nu-ți poți vota propria idee.", "You can't vote for your own idea.", "Tu ne peux pas voter pour ta propre idée.", "Non puoi votare la tua idea.", "No puedes votar tu propia idea.", "Du kannst nicht für deine eigene Idee stimmen."),
    "no_submission": ("Predarea nu există.", "Submission not found.", "Rendu introuvable.", "Consegna non trovata.", "Entrega no encontrada.", "Abgabe nicht gefunden."),
    "need_title": ("Scrie un titlu.", "Add a title.", "Ajoute un titre.", "Aggiungi un titolo.", "Añade un título.", "Füge einen Titel hinzu."),
    "bad_link": ("Linkul trebuie să înceapă cu https:// sau http://.", "The link must start with https:// or http://.", "Le lien doit commencer par https:// ou http://.", "Il link deve iniziare con https:// o http://.", "El enlace debe empezar por https:// o http://.", "Der Link muss mit https:// oder http:// beginnen."),
    "too_many_files": ("Poți încărca maxim {} fișiere.", "You can upload at most {} files.", "Tu peux envoyer au maximum {} fichiers.", "Puoi caricare al massimo {} file.", "Puedes subir como máximo {} archivos.", "Du kannst höchstens {} Dateien hochladen."),
    "file_too_big": ("Fișierul {} e prea mare (maxim 10 MB).", "File {} is too big (max 10 MB).", "Le fichier {} est trop gros (max 10 Mo).", "Il file {} è troppo grande (max 10 MB).", "El archivo {} es demasiado grande (máx. 10 MB).", "Die Datei {} ist zu groß (max. 10 MB)."),
    "bad_file_type": ("Tipul fișierului {} nu e acceptat.", "File type of {} is not allowed.", "Le type du fichier {} n'est pas accepté.", "Il tipo del file {} non è consentito.", "El tipo del archivo {} no está permitido.", "Der Dateityp von {} ist nicht erlaubt."),
    "empty_submission": ("Adaugă un fișier, un link sau un mesaj.", "Add a file, a link or a message.", "Ajoute un fichier, un lien ou un message.", "Aggiungi un file, un link o un messaggio.", "Añade un archivo, un enlace o un mensaje.", "Füge eine Datei, einen Link oder eine Nachricht hinzu."),
    "no_student": ("Studentul nu există.", "Student not found.", "Étudiant introuvable.", "Studente non trovato.", "Estudiante no encontrado.", "Student nicht gefunden."),
    "no_assignment": ("Tema nu există.", "Assignment not found.", "Devoir introuvable.", "Compito non trovato.", "Tarea no encontrada.", "Aufgabe nicht gefunden."),
    "bad_points": ("Punctele trebuie să fie între -100 și 100, diferite de 0.", "Points must be between -100 and 100, not 0.", "Les points doivent être entre -100 et 100, sauf 0.", "I punti devono essere tra -100 e 100, diversi da 0.", "Los puntos deben estar entre -100 y 100, distintos de 0.", "Punkte müssen zwischen -100 und 100 liegen, nicht 0."),
    "need_reason": ("Scrie motivul bonusului.", "Add a reason for the bonus.", "Indique la raison du bonus.", "Scrivi il motivo del bonus.", "Escribe el motivo del bonus.", "Gib einen Grund für den Bonus an."),
    "no_announcement": ("Anunțul nu există.", "Announcement not found.", "Annonce introuvable.", "Annuncio non trovato.", "Anuncio no encontrado.", "Ankündigung nicht gefunden."),
}
FIELD_NAMES = {
    "title": ("titlu", "title", "titre", "titolo", "título", "Titel"),
    "description": ("ce face aplicația", "what the app does", "ce que fait l'app", "cosa fa l'app", "qué hace la app", "was die App macht"),
    "audience": ("cine o folosește", "who uses it", "qui l'utilise", "chi la usa", "quién la usa", "wer sie nutzt"),
}


def lang_index() -> int:
    return ai.LANGS.index(current_lang.get())


def msg(key: str, *args) -> str:
    text = MESSAGES[key][lang_index()]
    return text.format(*args)


def fail(status: int, key: str, *args):
    raise HTTPException(status_code=status, detail=msg(key, *args))


@app.middleware("http")
async def language_middleware(request: Request, call_next):
    lang = request.headers.get("x-lang", "ro")
    current_lang.set(lang if lang in ai.LANGS else "ro")
    return await call_next(request)


app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")

# ---------------------------------------------------------------------------
# Stocare: în memorie, salvată într-un fișier JSON ca să supraviețuiască
# repornirilor. Sesiunile se salvează doar ca hash al tokenului.
# ---------------------------------------------------------------------------

_lock = threading.Lock()
db = {
    "users": {}, "sessions": {}, "prefs": {}, "drafts": [],
    "questions": [], "proposals": [], "submissions": [],
    "messages": [], "assignments": [], "announcements": [], "bonuses": [],
    "next_id": 1,
}
SESSION_DAYS = 60


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
# Conturi: email + parolă (sau Google, dacă e configurat GOOGLE_CLIENT_ID).
# Trainerul e recunoscut după email (TRAINER_EMAILS) sau după codul de
# trainer dat la crearea contului. Dacă e setat CLASS_CODE, doar cine are
# codul clasei își poate face cont.
# ---------------------------------------------------------------------------

TRAINER_EMAILS = {e.strip().lower() for e in os.environ.get("TRAINER_EMAILS", "").split(",") if e.strip()}
CLASS_CODE = os.environ.get("CLASS_CODE", "").strip()
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
MIN_PASSWORD = 8
MAX_FAILED = 5          # încercări greșite permise…
LOCK_SECONDS = 10 * 60  # …într-o fereastră de 10 minute
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_failed: dict[str, list] = {}


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(max_length=200)
    class_code: Optional[str] = Field(None, max_length=100)
    trainer_code: Optional[str] = Field(None, max_length=100)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(max_length=200)


class GoogleIn(BaseModel):
    credential: str = Field(min_length=10, max_length=5000)
    class_code: Optional[str] = Field(None, max_length=100)


def hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def same(a: str, b: str) -> bool:
    return hmac.compare_digest((a or "").encode(), (b or "").encode())


def clean_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        fail(400, "bad_email")
    return email


def check_class_code(code: Optional[str]):
    if CLASS_CODE and not same((code or "").strip(), CLASS_CODE):
        fail(403, "wrong_class_code")


def role_for(email: str, trainer_code: Optional[str] = None) -> str:
    if email in TRAINER_EMAILS or (trainer_code and same(trainer_code.strip(), TRAINER_CODE)):
        return "trainer"
    return "student"


def throttle(email: str):
    """Blochează temporar contul după prea multe parole greșite."""
    recent = [t for t in _failed.get(email, []) if t > datetime.now(timezone.utc).timestamp() - LOCK_SECONDS]
    _failed[email] = recent
    if len(recent) >= MAX_FAILED:
        fail(429, "too_many_attempts")


def start_session(user: dict) -> dict:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc).timestamp() + SESSION_DAYS * 86400
    # Sesiunea rămâne validă și după repornirea serverului; „Ieși” o șterge
    db["sessions"][token_hash(token)] = {
        "name": user["name"], "role": user["role"], "key": user["email"],
        "expires": datetime.fromtimestamp(expires, timezone.utc).isoformat(timespec="seconds"),
    }
    save_db()
    return {"token": token, "name": user["name"], "role": user["role"]}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(authorization: Optional[str] = Header(None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = db["sessions"].get(token_hash(token)) if token else None
    if not user or user.get("expires", "") < now():
        fail(401, "login_again")
    return user


def require_trainer(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "trainer":
        fail(403, "trainer_only")
    return user


def require_student(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "student":
        fail(403, "student_only")
    return user


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.post("/api/register", status_code=201)
def register(body: RegisterIn):
    name = body.name.strip()
    if not name:
        fail(400, "need_name")
    email = clean_email(body.email)
    if len(body.password) < MIN_PASSWORD:
        fail(400, "short_password")
    if body.trainer_code and body.trainer_code.strip() and not same(body.trainer_code.strip(), TRAINER_CODE):
        fail(403, "wrong_code")
    role = role_for(email, body.trainer_code)
    if role == "student":
        check_class_code(body.class_code)
    with _lock:
        if email in db["users"]:
            fail(409, "email_taken")
        salt = secrets.token_bytes(16)
        db["users"][email] = {"name": name, "email": email, "role": role, "salt": salt.hex(),
                              "hash": hash_password(body.password, salt), "created_at": now()}
        return start_session(db["users"][email])


@app.post("/api/login")
def login(body: LoginIn):
    email = clean_email(body.email)
    throttle(email)
    user = db["users"].get(email)
    # Același mesaj pentru email greșit și parolă greșită: nu dezvăluim cine are cont
    ok = bool(user and user.get("hash")) and same(
        hash_password(body.password, bytes.fromhex(user["salt"])), user["hash"])
    if not ok:
        _failed.setdefault(email, []).append(datetime.now(timezone.utc).timestamp())
        fail(401, "wrong_login")
    _failed.pop(email, None)
    with _lock:
        user["role"] = role_for(email) if user["role"] == "student" else user["role"]
        return start_session(user)


@app.post("/api/auth/google")
def google_login(body: GoogleIn):
    """Intrare cu contul Google: verificăm pe server tokenul semnat de Google."""
    if not GOOGLE_CLIENT_ID:
        fail(404, "google_off")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
        info = id_token.verify_oauth2_token(body.credential, google_requests.Request(), GOOGLE_CLIENT_ID)
    except Exception:
        fail(401, "google_failed")
    if not info.get("email_verified"):
        fail(401, "google_failed")
    email = clean_email(info.get("email", ""))
    with _lock:
        user = db["users"].get(email)
        if user is None:
            role = role_for(email)
            if role == "student":
                check_class_code(body.class_code)
            user = db["users"][email] = {"name": (info.get("name") or email.split("@")[0])[:60], "email": email,
                                         "role": role, "google": True, "created_at": now()}
        return start_session(user)


class PasswordIn(BaseModel):
    current: Optional[str] = Field(None, max_length=200)
    new: str = Field(max_length=200)


@app.post("/api/me/password")
def change_password(body: PasswordIn, user: dict = Depends(current_user)):
    """Schimbă parola. Conturile create cu Google își pot pune o parolă fără cea veche."""
    account = db["users"].get(user["key"])
    if account is None:
        fail(401, "login_again")
    if account.get("hash") and not same(hash_password(body.current or "", bytes.fromhex(account["salt"])), account["hash"]):
        fail(403, "wrong_current")
    if len(body.new) < MIN_PASSWORD:
        fail(400, "short_password")
    with _lock:
        salt = secrets.token_bytes(16)
        account.update(salt=salt.hex(), hash=hash_password(body.new, salt))
        save_db()
    return {"ok": True}


class ResetOut(BaseModel):
    temporary_password: str


@app.post("/api/students/{student_key}/reset-password")
def reset_password(student_key: str, user: dict = Depends(require_trainer)) -> ResetOut:
    """Trainerul generează o parolă temporară pentru un student care a uitat-o."""
    if student_key not in known_students():
        fail(404, "no_student")
    temp = secrets.token_urlsafe(9)
    with _lock:
        salt = secrets.token_bytes(16)
        db["users"][student_key].update(salt=salt.hex(), hash=hash_password(temp, salt))
        # Sesiunile vechi ale studentului se închid
        db["sessions"] = {h: sess for h, sess in db["sessions"].items() if sess["key"] != student_key}
        save_db()
    return ResetOut(temporary_password=temp)


@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(None)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    with _lock:
        if db["sessions"].pop(token_hash(token), None):
            save_db()
    return {"ok": True}


class PrefsIn(BaseModel):
    lang: Optional[str] = Field(None, max_length=5)
    hide_from_leaderboard: Optional[bool] = None


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    account = db["users"].get(user["key"], {})
    return {"name": user["name"], "role": user["role"], "email": user["key"],
            "has_password": bool(account.get("hash")), "prefs": db["prefs"].get(user["key"], {})}


@app.patch("/api/me")
def update_prefs(body: PrefsIn, user: dict = Depends(current_user)):
    with _lock:
        prefs = db["prefs"].setdefault(user["key"], {})
        if body.lang in ai.LANGS:
            prefs["lang"] = body.lang
        if body.hide_from_leaderboard is not None:
            prefs["hide_from_leaderboard"] = body.hide_from_leaderboard
        save_db()
    return {"prefs": prefs}


@app.get("/api/config")
def config():
    """Ce poate interfața: dacă AI-ul e disponibil și ce topicuri există."""
    return {"ai": ai.available(), "topics": TOPICS, "google_client_id": GOOGLE_CLIENT_ID or None,
            "class_code_required": bool(CLASS_CODE)}


# ---------------------------------------------------------------------------
# Întrebări: le vede doar autorul și trainerul.
# Categoriile sunt topicurile de vibe coding (textele lor stau în interfață).
# ---------------------------------------------------------------------------

TOPICS = [
    "prompting", "context", "planning", "claude-code", "artifacts", "debugging",
    "git", "security", "data", "deploy", "testing", "ai-apis", "mcp", "design", "other",
]


class QuestionIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    category: str = "other"
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
    return TOPICS


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
        fail(400, "too_short")
    with _lock:
        q = {
            "id": next_id(),
            "text": text,
            "category": body.category if body.category in TOPICS else "other",
            "anonymous": body.anonymous,
            "author": user["name"],
            "author_key": user["key"],
            "created_at": now(),
            "answer": None,
            "answered_at": None,
            "ai_answer": None,
            "ai_answered_at": None,
        }
        db["questions"].append(q)
        save_db()
    return question_view(q, user)


def find_question(question_id: int) -> dict:
    q = next((q for q in db["questions"] if q["id"] == question_id), None)
    if not q:
        fail(404, "no_question")
    return q


@app.post("/api/questions/{question_id}/answer")
def answer_question(question_id: int, body: AnswerIn, user: dict = Depends(require_trainer)):
    with _lock:
        q = find_question(question_id)
        q["answer"] = body.text.strip()
        q["answered_at"] = now()
        save_db()
    return question_view(q, user)


@app.post("/api/questions/{question_id}/ai-answer")
def ai_answer_question(question_id: int, user: dict = Depends(current_user)):
    """Răspuns rapid de la tutorul AI, cât timp studentul așteaptă trainerul.
    Se generează o singură dată per întrebare și se păstrează."""
    q = find_question(question_id)
    if user["role"] != "trainer" and q["author_key"] != user["key"]:
        fail(403, "not_yours")
    if q.get("ai_answer"):
        return question_view(q, user)
    if not ai.available():
        fail(503, "ai_off")
    answer = ai.answer_question(q["text"], q["category"], current_lang.get())
    if not answer:
        fail(502, "ai_failed")
    with _lock:
        q["ai_answer"] = answer
        q["ai_answered_at"] = now()
        save_db()
    return question_view(q, user)


# ---------------------------------------------------------------------------
# Teme & proiecte: spațiul privat student ↔ trainer.
# Fișierele stau pe server cu nume aleatorii și se descarcă doar prin API,
# după verificarea accesului (autorul sau trainerul).
# ---------------------------------------------------------------------------

SUBMISSION_KINDS = ["homework", "project", "other"]
REVIEW_STATUSES = ["sent", "received", "reviewed", "redo"]
# „Gata când” din fișa temei
CHECKLIST = ["features", "privacy", "ai_consent", "github_readme", "no_keys", "trainer_access"]
MAX_FILES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".txt", ".md",
    ".py", ".js", ".ts", ".html", ".css", ".json", ".csv", ".ipynb",
    ".docx", ".pptx", ".xlsx",
}


class ReviewIn(BaseModel):
    status: str = Field(pattern="^(received|reviewed|redo)$")
    feedback: str = Field("", max_length=4000)


def safe_filename(name: str) -> str:
    name = Path(name or "fisier").name
    name = re.sub(r"[^\w.\- ]", "_", name).strip() or "fisier"
    return name[-120:]


def submission_view(sub: dict, user: dict) -> dict:
    view = {k: v for k, v in sub.items() if k not in ("author_key", "files")}
    view["files"] = [{k: f[k] for k in ("id", "name", "size")} for f in sub["files"]]
    view["mine"] = sub["author_key"] == user["key"]
    return view


def find_submission(submission_id: int, user: dict) -> dict:
    sub = next((x for x in db["submissions"] if x["id"] == submission_id), None)
    # Pentru altcineva, o predare străină „nu există”: nu confirmăm nici că există
    if not sub or (user["role"] != "trainer" and sub["author_key"] != user["key"]):
        fail(404, "no_submission")
    return sub


@app.get("/api/submissions")
def list_submissions(user: dict = Depends(current_user)):
    items = db["submissions"]
    if user["role"] != "trainer":
        items = [x for x in items if x["author_key"] == user["key"]]
    return [submission_view(x, user) for x in reversed(items)]


@app.post("/api/submissions", status_code=201)
async def create_submission(
    kind: str = Form("homework"),
    title: str = Form("", max_length=200),
    note: str = Form("", max_length=4000),
    link: str = Form("", max_length=500),
    checklist: list[str] = Form([]),
    assignment_id: Optional[int] = Form(None),
    files: list[UploadFile] = File([]),
    user: dict = Depends(require_student),
):
    title, note, link = title.strip(), note.strip(), link.strip()
    if not title:
        fail(400, "need_title")
    if link and not re.match(r"^https?://", link, re.IGNORECASE):
        fail(400, "bad_link")
    files = [f for f in files if f.filename]
    if len(files) > MAX_FILES:
        fail(400, "too_many_files", MAX_FILES)
    if not (files or link or note):
        fail(400, "empty_submission")
    if assignment_id is not None and not any(a["id"] == assignment_id for a in db["assignments"]):
        fail(404, "no_assignment")

    # Validăm tot înainte să scriem ceva pe disc
    accepted = []
    for f in files:
        name = safe_filename(f.filename)
        if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
            fail(400, "bad_file_type", name)
        content = await f.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            fail(400, "file_too_big", name)
        accepted.append((name, content))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_files = []
    for name, content in accepted:
        stored = uuid.uuid4().hex
        (UPLOAD_DIR / stored).write_bytes(content)
        stored_files.append({"id": uuid.uuid4().hex[:12], "name": name, "size": len(content), "stored": stored})

    with _lock:
        sub = {
            "id": next_id(),
            "kind": kind if kind in SUBMISSION_KINDS else "other",
            "title": title,
            "note": note,
            "link": link,
            "checklist": [c for c in CHECKLIST if c in checklist],
            "assignment_id": assignment_id,
            "files": stored_files,
            "author": user["name"],
            "author_key": user["key"],
            "created_at": now(),
            "status": "sent",
            "feedback": None,
            "reviewed_at": None,
        }
        db["submissions"].append(sub)
        save_db()
    return submission_view(sub, user)


@app.get("/api/submissions/{submission_id}/files/{file_id}")
def download_file(submission_id: int, file_id: str, user: dict = Depends(current_user)):
    sub = find_submission(submission_id, user)
    f = next((f for f in sub["files"] if f["id"] == file_id), None)
    path = UPLOAD_DIR / f["stored"] if f else None
    if not path or not path.exists():
        fail(404, "no_submission")
    # Mereu descărcare, niciodată afișat în pagină (un .html încărcat nu poate rula cod)
    return FileResponse(path, filename=f["name"], media_type="application/octet-stream",
                        headers={"X-Content-Type-Options": "nosniff"})


@app.post("/api/submissions/{submission_id}/review")
def review_submission(submission_id: int, body: ReviewIn, user: dict = Depends(require_trainer)):
    with _lock:
        sub = find_submission(submission_id, user)
        sub["status"] = body.status
        sub["feedback"] = body.feedback.strip() or None
        sub["reviewed_at"] = now()
        save_db()
    return submission_view(sub, user)


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


def is_withdrawn(p: dict) -> bool:
    return p.get("status") == "withdrawn"


def proposal_view(p: dict, user: dict) -> dict:
    view = {k: v for k, v in p.items() if k not in ("author_key", "voters")}
    view["status"] = p.get("status", "active")
    view["votes"] = len(p["voters"])
    view["voted"] = user["key"] in p["voters"]
    view["mine"] = p["author_key"] == user["key"]
    return view


@app.post("/api/proposals/refine")
def refine_proposal(body: ProposalDraft, user: dict = Depends(require_student)):
    if not (body.title.strip() or body.description.strip() or body.audience.strip()):
        fail(400, "empty_idea")
    return ai.refine(body.title, body.description, body.audience, current_lang.get())


@app.post("/api/proposals", status_code=201)
def submit_proposal(body: ProposalIn, user: dict = Depends(require_student)):
    if not body.approved:
        fail(400, "approve_first")
    fields = {k: getattr(body, k).strip() for k in ("title", "description", "audience")}
    empty = [FIELD_NAMES[k][lang_index()] for k, v in fields.items() if not v]
    if empty:
        fail(400, "missing", ", ".join(empty))
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
    """Clasa vede doar propunerile active; autorul și trainerul le văd și pe cele retrase."""
    return [proposal_view(p, user) for p in reversed(db["proposals"])
            if not is_withdrawn(p) or p["author_key"] == user["key"] or user["role"] == "trainer"]


def find_proposal(proposal_id: int) -> dict:
    p = next((p for p in db["proposals"] if p["id"] == proposal_id), None)
    if not p:
        fail(404, "no_proposal")
    return p


@app.post("/api/proposals/{proposal_id}/vote")
def toggle_vote(proposal_id: int, user: dict = Depends(require_student)):
    with _lock:
        p = find_proposal(proposal_id)
        if is_withdrawn(p):
            fail(400, "withdrawn")
        if p["author_key"] == user["key"]:
            fail(400, "own_vote")
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
        if is_withdrawn(p) and not p["chosen"]:
            fail(400, "withdrawn")
        p["chosen"] = not p["chosen"]
        p["chosen_at"] = now() if p["chosen"] else None
        save_db()
    return proposal_view(p, user)


class WithdrawIn(BaseModel):
    reason: str = Field("resolved", pattern="^(resolved|other)$")
    note: str = Field("", max_length=300)


def own_proposal(proposal_id: int, user: dict) -> dict:
    p = find_proposal(proposal_id)
    if p["author_key"] != user["key"]:
        fail(403, "not_author")
    return p


@app.post("/api/proposals/{proposal_id}/withdraw")
def withdraw_proposal(proposal_id: int, body: WithdrawIn, user: dict = Depends(require_student)):
    """Autorul își retrage propunerea (de ex. a rezolvat singur problema). Iese din cutia publică."""
    with _lock:
        p = own_proposal(proposal_id, user)
        p.update(status="withdrawn", withdrawn_reason=body.reason,
                 withdrawn_note=body.note.strip() or None, withdrawn_at=now())
        save_db()
    return proposal_view(p, user)


@app.post("/api/proposals/{proposal_id}/restore")
def restore_proposal(proposal_id: int, user: dict = Depends(require_student)):
    with _lock:
        p = own_proposal(proposal_id, user)
        p.update(status="active", withdrawn_reason=None, withdrawn_note=None, withdrawn_at=None)
        save_db()
    return proposal_view(p, user)


# ---------------------------------------------------------------------------
# Ciorne: propunerile la care încă lucrezi, salvate pe server (doar ale tale).
# ---------------------------------------------------------------------------

MAX_DRAFTS = 20


class DraftIn(BaseModel):
    title: str = Field("", max_length=200)
    description: str = Field("", max_length=4000)
    audience: str = Field("", max_length=500)


def draft_view(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "owner"}


def own_draft(draft_id: int, user: dict) -> dict:
    d = next((d for d in db["drafts"] if d["id"] == draft_id), None)
    # O ciornă străină „nu există”, ca să nu confirmăm nici măcar că e acolo
    if not d or d["owner"] != user["key"]:
        fail(404, "no_draft")
    return d


@app.get("/api/drafts")
def list_drafts(user: dict = Depends(current_user)):
    mine = [d for d in db["drafts"] if d["owner"] == user["key"]]
    return [draft_view(d) for d in sorted(mine, key=lambda d: d["updated_at"], reverse=True)]


@app.post("/api/drafts", status_code=201)
def create_draft(body: DraftIn, user: dict = Depends(current_user)):
    with _lock:
        if sum(1 for d in db["drafts"] if d["owner"] == user["key"]) >= MAX_DRAFTS:
            fail(400, "too_many_drafts", MAX_DRAFTS)
        d = {"id": next_id(), "owner": user["key"], **body.model_dump(), "created_at": now(), "updated_at": now()}
        db["drafts"].append(d)
        save_db()
    return draft_view(d)


@app.put("/api/drafts/{draft_id}")
def update_draft(draft_id: int, body: DraftIn, user: dict = Depends(current_user)):
    with _lock:
        d = own_draft(draft_id, user)
        d.update(**body.model_dump(), updated_at=now())
        save_db()
    return draft_view(d)


@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: int, user: dict = Depends(current_user)):
    with _lock:
        d = own_draft(draft_id, user)
        db["drafts"].remove(d)
        save_db()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Mesaje directe: fiecare student are o conversație privată cu trainerul.
# Studentul vede doar conversația lui; trainerul le vede pe toate.
# ---------------------------------------------------------------------------


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def known_students() -> dict:
    """Toți studenții care au cont, după email."""
    return {k: u["name"] for k, u in db["users"].items() if u.get("role") == "student" and u.get("email")}


def thread_view(student_key: str, user: dict) -> list:
    return [
        {k: m[k] for k in ("id", "from_role", "from_name", "text", "created_at")}
        | {"mine": m["from_role"] == user["role"]}
        for m in db["messages"] if m["student_key"] == student_key
    ]


def mark_read(student_key: str, role: str):
    changed = False
    for m in db["messages"]:
        if m["student_key"] == student_key and m["from_role"] != role and not m.get(f"read_{role}"):
            m[f"read_{role}"] = True
            changed = True
    if changed:
        save_db()


def add_message(student_key: str, user: dict, text: str) -> dict:
    text = text.strip()
    if not text:
        fail(400, "too_short")
    m = {
        "id": next_id(), "student_key": student_key, "from_role": user["role"],
        "from_name": user["name"], "text": text, "created_at": now(),
        f"read_{user['role']}": True,
    }
    db["messages"].append(m)
    save_db()
    return m


@app.get("/api/dm")
def list_threads(user: dict = Depends(current_user)):
    """Student: conversația lui. Trainer: lista conversațiilor cu necitite."""
    if user["role"] == "student":
        with _lock:
            mark_read(user["key"], "student")
            return {"messages": thread_view(user["key"], user)}
    students = known_students()
    threads = []
    for key, name in students.items():
        msgs = [m for m in db["messages"] if m["student_key"] == key]
        last = msgs[-1] if msgs else None
        threads.append({
            "student_key": key, "name": name,
            "last": last["text"][:120] if last else None,
            "last_at": last["created_at"] if last else None,
            "unread": sum(1 for m in msgs if m["from_role"] == "student" and not m.get("read_trainer")),
        })
    threads.sort(key=lambda t: (t["last_at"] or "", t["name"]), reverse=True)
    return {"threads": threads}


@app.get("/api/dm/unread")
def unread_count(user: dict = Depends(current_user)):
    if user["role"] == "student":
        n = sum(1 for m in db["messages"] if m["student_key"] == user["key"]
                and m["from_role"] == "trainer" and not m.get("read_student"))
    else:
        n = sum(1 for m in db["messages"] if m["from_role"] == "student" and not m.get("read_trainer"))
    return {"unread": n}


@app.get("/api/dm/{student_key}")
def get_thread(student_key: str, user: dict = Depends(require_trainer)):
    if student_key not in known_students():
        fail(404, "no_student")
    with _lock:
        mark_read(student_key, "trainer")
        return {"name": known_students()[student_key], "messages": thread_view(student_key, user)}


@app.post("/api/dm", status_code=201)
def send_to_trainer(body: MessageIn, user: dict = Depends(require_student)):
    with _lock:
        m = add_message(user["key"], user, body.text)
    return thread_view(user["key"], user)[-1] if m else None


@app.post("/api/dm/{student_key}", status_code=201)
def send_to_student(student_key: str, body: MessageIn, user: dict = Depends(require_trainer)):
    if student_key not in known_students():
        fail(404, "no_student")
    with _lock:
        add_message(student_key, user, body.text)
    return thread_view(student_key, user)[-1]


# ---------------------------------------------------------------------------
# Teme anunțate de trainer (cu termen și puncte) și anunțuri pentru clasă.
# ---------------------------------------------------------------------------


class AssignmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=4000)
    due_at: Optional[str] = Field(None, max_length=40)
    points: int = Field(20, ge=0, le=100)


class AnnouncementIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    pinned: bool = False


def parse_due(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


@app.get("/api/assignments")
def list_assignments(user: dict = Depends(current_user)):
    out = []
    for a in reversed(db["assignments"]):
        mine = [x for x in db["submissions"] if x.get("assignment_id") == a["id"]
                and (user["role"] == "trainer" or x["author_key"] == user["key"])]
        out.append({**a, "submitted": len(mine) if user["role"] == "trainer" else bool(mine)})
    return out


@app.post("/api/assignments", status_code=201)
def create_assignment(body: AssignmentIn, user: dict = Depends(require_trainer)):
    with _lock:
        a = {"id": next_id(), "title": body.title.strip(), "description": body.description.strip(),
             "due_at": parse_due(body.due_at), "points": body.points, "created_at": now()}
        db["assignments"].append(a)
        save_db()
    return a


@app.delete("/api/assignments/{assignment_id}")
def delete_assignment(assignment_id: int, user: dict = Depends(require_trainer)):
    with _lock:
        before = len(db["assignments"])
        db["assignments"] = [a for a in db["assignments"] if a["id"] != assignment_id]
        if len(db["assignments"]) == before:
            fail(404, "no_assignment")
        save_db()
    return {"ok": True}


@app.get("/api/announcements")
def list_announcements(user: dict = Depends(current_user)):
    return sorted(db["announcements"], key=lambda a: (a["pinned"], a["created_at"]), reverse=True)


@app.post("/api/announcements", status_code=201)
def create_announcement(body: AnnouncementIn, user: dict = Depends(require_trainer)):
    with _lock:
        a = {"id": next_id(), "text": body.text.strip(), "pinned": body.pinned,
             "author": user["name"], "created_at": now()}
        db["announcements"].append(a)
        save_db()
    return a


@app.delete("/api/announcements/{announcement_id}")
def delete_announcement(announcement_id: int, user: dict = Depends(require_trainer)):
    with _lock:
        before = len(db["announcements"])
        db["announcements"] = [a for a in db["announcements"] if a["id"] != announcement_id]
        if len(db["announcements"]) == before:
            fail(404, "no_announcement")
        save_db()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Puncte & badge-uri (calculate pe server, vezi points.py) + bonusuri.
# ---------------------------------------------------------------------------


class BonusIn(BaseModel):
    student_key: str = Field(min_length=1, max_length=60)
    points: int = Field(ge=-100, le=100)
    reason: str = Field("", max_length=200)


def points_summary(key: str, all_points: dict) -> dict:
    data = all_points.get(key, {"total": 0, "events": []})
    total = data["total"]
    return {
        "total": total,
        "level": points.level_for(total),
        "badges": points.badges(key, db, total),
        "events": sorted(data["events"], key=lambda e: e["at"] or "", reverse=True)[:30],
    }


@app.get("/api/points/me")
def my_points(user: dict = Depends(require_student)):
    return {**points_summary(user["key"], points.compute(db)), "rules": points.RULES}


@app.get("/api/points/{student_key}")
def student_points(student_key: str, user: dict = Depends(require_trainer)):
    if student_key not in known_students():
        fail(404, "no_student")
    return points_summary(student_key, points.compute(db))


@app.get("/api/leaderboard")
def leaderboard(user: dict = Depends(current_user)):
    """Public pentru clasă. Cine a ales „ascunde-mă” nu apare (dar își vede locul)."""
    all_points = points.compute(db)
    students = known_students()
    rows = []
    for key, name in students.items():
        total = all_points.get(key, {"total": 0})["total"]
        rows.append({"key": key, "name": name, "total": total, "level": points.level_for(total)["index"],
                     "hidden": db["prefs"].get(key, {}).get("hide_from_leaderboard", False)})
    rows.sort(key=lambda r: (-r["total"], r["name"].casefold()))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    visible = [r for r in rows if not r["hidden"] or user["role"] == "trainer" or r["key"] == user["key"]]
    out = []
    for r in visible[:50]:
        row = {k: r[k] for k in ("rank", "name", "total", "level")}
        row["me"] = r["key"] == user["key"]
        if user["role"] == "trainer":
            row["key"] = r["key"]
            row["hidden"] = r["hidden"]
        out.append(row)
    return out


@app.post("/api/points/bonus", status_code=201)
def give_bonus(body: BonusIn, user: dict = Depends(require_trainer)):
    if body.student_key not in known_students():
        fail(404, "no_student")
    if body.points == 0:
        fail(400, "bad_points")
    if not body.reason.strip():
        fail(400, "need_reason")
    with _lock:
        b = {"id": next_id(), "student_key": body.student_key, "points": body.points,
             "reason": body.reason.strip(), "by": user["name"], "created_at": now()}
        db["bonuses"].append(b)
        save_db()
    return b


@app.get("/api/students")
def list_students(user: dict = Depends(require_trainer)):
    all_points = points.compute(db)
    return [{"key": k, "name": n, "total": all_points.get(k, {"total": 0})["total"]}
            for k, n in sorted(known_students().items(), key=lambda kv: kv[1].casefold())]


# ---------------------------------------------------------------------------
# AI News: știri din lumea AI, filtrate (și, cu cheie, alese de Claude).
# ---------------------------------------------------------------------------

_news_refresh = {"at": 0.0}


@app.get("/api/news")
def get_news(refresh: bool = False, user: dict = Depends(current_user)):
    import time
    # Reîmprospătare manuală cel mult o dată la 10 minute, ca să nu încărcăm sursele
    force = refresh and time.time() - _news_refresh["at"] > 600
    if force:
        _news_refresh["at"] = time.time()
    data = news.get_items(force=force)
    curated = news.curate(data["items"], current_lang.get(), ai)
    return {**data, **curated}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
