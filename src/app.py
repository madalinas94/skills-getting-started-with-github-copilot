"""
Cutia Clasei · platforma internă a cursului de vibe coding.

Spațiul privat (student ↔ trainer): mesaje directe, întrebări, teme & proiecte.
Spațiul public (toată clasa): cutia de idei, AI News, ghidul, clasamentul.
Toate regulile de acces se verifică aici, pe server.
"""

import contextvars
from contextlib import asynccontextmanager
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
    from . import ai, digest, news, points, repocheck, supa, tools
except ImportError:  # rulare directă: python app.py
    import ai
    import digest
    import repocheck
    import tools
    import news
    import points
    import supa

DATA_FILE = Path(os.environ.get("CUTIA_DATA", current_dir.parent / "data" / "cutia.json"))
UPLOAD_DIR = Path(os.environ.get("CUTIA_UPLOADS", DATA_FILE.parent / "uploads"))
# Un cod de trainer scris în README sau în .env.example îl știe oricine: îl ignorăm
WEAK_TRAINER_CODES = {"trainer", "schimba-ma", "secret", "parola", "password", "admin", "123456"}
TRAINER_CODE = os.environ.get("TRAINER_CODE", "").strip()
if TRAINER_CODE.lower() in WEAK_TRAINER_CODES and os.environ.get("CUTIA_ALLOW_WEAK_CODE") != "1" or len(TRAINER_CODE) < 6:
    TRAINER_CODE = ""

@asynccontextmanager
async def lifespan(_app):
    start_byte()  # robotul de știri (definit mai jos, la „Byte”)
    yield


app = FastAPI(title="Cutia Clasei API",
              description="Întrebări pentru trainer și propuneri de proiecte", lifespan=lifespan)

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
    "confirm_email_first": ("Confirmă întâi emailul: apasă linkul primit de la noi, apoi intră.", "Confirm your email first: click the link we sent you, then sign in.", "Confirme d'abord ton e-mail : clique sur le lien reçu, puis connecte-toi.", "Conferma prima l'email: clicca il link che ti abbiamo inviato, poi accedi.", "Confirma primero tu correo: pulsa el enlace que te enviamos y luego inicia sesión.", "Bestätige zuerst deine E-Mail: Klick auf den Link, den wir dir geschickt haben, dann melde dich an."),
    "weak_password": ("Parola e prea slabă. Alege una mai lungă, cu litere și cifre.", "That password is too weak. Pick a longer one with letters and numbers.", "Ce mot de passe est trop faible. Choisis-en un plus long, avec lettres et chiffres.", "La password è troppo debole. Scegline una più lunga, con lettere e numeri.", "La contraseña es demasiado débil. Elige una más larga, con letras y números.", "Das Passwort ist zu schwach. Wähl ein längeres mit Buchstaben und Zahlen."),
    "auth_down": ("Serviciul de conturi (Supabase) nu răspunde. Încearcă peste un minut.", "The account service (Supabase) isn't responding. Try again in a minute.", "Le service de comptes (Supabase) ne répond pas. Réessaie dans une minute.", "Il servizio account (Supabase) non risponde. Riprova tra un minuto.", "El servicio de cuentas (Supabase) no responde. Inténtalo en un minuto.", "Der Kontodienst (Supabase) antwortet nicht. Versuch es in einer Minute."),
    "link_expired": ("Linkul a expirat sau a fost deja folosit. Cere unul nou.", "This link has expired or was already used. Ask for a new one.", "Ce lien a expiré ou a déjà été utilisé. Demandes-en un nouveau.", "Il link è scaduto o è già stato usato. Chiedine uno nuovo.", "El enlace ha caducado o ya se usó. Pide uno nuevo.", "Der Link ist abgelaufen oder wurde schon benutzt. Fordere einen neuen an."),
    "supabase_off": ("Conturile Supabase nu sunt configurate pe server.", "Supabase accounts aren't configured on the server.", "Les comptes Supabase ne sont pas configurés sur le serveur.", "Gli account Supabase non sono configurati sul server.", "Las cuentas de Supabase no están configuradas en el servidor.", "Supabase-Konten sind auf dem Server nicht eingerichtet."),
    "not_github": ("Pune linkul repo-ului de GitHub, de forma https://github.com/nume/repo.", "Paste your GitHub repo link, like https://github.com/name/repo.", "Colle le lien de ton dépôt GitHub, comme https://github.com/nom/depot.", "Incolla il link del repo GitHub, tipo https://github.com/nome/repo.", "Pega el enlace de tu repo de GitHub, como https://github.com/nombre/repo.", "Füge den Link zu deinem GitHub-Repo ein, z. B. https://github.com/name/repo."),
    "repo_not_found": ("Nu găsesc repo-ul. Verifică linkul sau fă-l public (Settings → General → Danger Zone → Change visibility).", "Can't find that repo. Check the link or make it public (Settings → General → Danger Zone → Change visibility).", "Dépôt introuvable. Vérifie le lien ou rends-le public (Settings → General → Danger Zone → Change visibility).", "Repo non trovato. Controlla il link o rendilo pubblico (Settings → General → Danger Zone → Change visibility).", "No encuentro el repo. Revisa el enlace o hazlo público (Settings → General → Danger Zone → Change visibility).", "Repo nicht gefunden. Prüf den Link oder mach es öffentlich (Settings → General → Danger Zone → Change visibility)."),
    "github_busy": ("GitHub ne-a limitat cererile. Mai încearcă peste câteva minute.", "GitHub is limiting our requests. Try again in a few minutes.", "GitHub limite nos requêtes. Réessaie dans quelques minutes.", "GitHub sta limitando le richieste. Riprova tra qualche minuto.", "GitHub está limitando las peticiones. Inténtalo en unos minutos.", "GitHub begrenzt gerade die Anfragen. Versuch es in ein paar Minuten."),
    "github_down": ("Nu am putut citi repo-ul de pe GitHub acum. Încearcă din nou.", "Couldn't read the repo from GitHub right now. Try again.", "Impossible de lire le dépôt sur GitHub. Réessaie.", "Impossibile leggere il repo da GitHub ora. Riprova.", "No se pudo leer el repo de GitHub. Inténtalo de nuevo.", "Das Repo konnte gerade nicht von GitHub gelesen werden. Versuch es nochmal."),
    "slow_down": ("Încă puțin: poți încerca din nou peste {} secunde.", "Hang on: you can try again in {} seconds.", "Un instant : tu pourras réessayer dans {} secondes.", "Un attimo: puoi riprovare tra {} secondi.", "Un momento: puedes intentarlo en {} segundos.", "Moment: du kannst es in {} Sekunden wieder versuchen."),
    "need_error": ("Lipește mesajul de eroare sau adaugă o captură de ecran.", "Paste the error message or add a screenshot.", "Colle le message d'erreur ou ajoute une capture d'écran.", "Incolla il messaggio di errore o aggiungi uno screenshot.", "Pega el mensaje de error o añade una captura.", "Füge die Fehlermeldung oder einen Screenshot ein."),
    "bad_image": ("Captura trebuie să fie PNG, JPG sau WebP, de maxim 5 MB.", "The screenshot must be PNG, JPG or WebP, max 5 MB.", "La capture doit être en PNG, JPG ou WebP, 5 Mo max.", "Lo screenshot deve essere PNG, JPG o WebP, max 5 MB.", "La captura debe ser PNG, JPG o WebP, de 5 MB como máximo.", "Der Screenshot muss PNG, JPG oder WebP sein, max. 5 MB."),
    "no_item": ("Nu există.", "Not found.", "Introuvable.", "Non trovato.", "No encontrado.", "Nicht gefunden."),
    "own_like": ("Nu-ți poți aprecia propriul prompt.", "You can't like your own prompt.", "Tu ne peux pas aimer ton propre prompt.", "Non puoi mettere like al tuo prompt.", "No puedes dar me gusta a tu propio prompt.", "Du kannst deinen eigenen Prompt nicht liken."),
    "too_many_posts": ("Ai atins limita de {}. Șterge unul mai vechi.", "You've reached the limit of {}. Delete an older one.", "Tu as atteint la limite de {}. Supprimes-en un ancien.", "Hai raggiunto il limite di {}. Eliminane uno vecchio.", "Has llegado al límite de {}. Borra uno anterior.", "Du hast das Limit von {} erreicht. Lösch einen älteren."),
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
    "supabase_pending": {}, "digests": [], "next_id": 1,
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
    # Scriem într-un fișier temporar și apoi îl înlocuim dintr-o mișcare:
    # dacă serverul se oprește la jumătate, datele vechi rămân întregi
    tmp = DATA_FILE.with_name(f"{DATA_FILE.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, DATA_FILE)


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


def valid_trainer_code(code: Optional[str]) -> bool:
    return bool(TRAINER_CODE and code and same(code.strip(), TRAINER_CODE))


def role_for(email: str, trainer_code: Optional[str] = None) -> str:
    if email in TRAINER_EMAILS or valid_trainer_code(trainer_code):
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


@app.get("/api/health")
def health():
    """Pentru hosting: serverul răspunde (fără date despre nimeni)."""
    return {"ok": True}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.post("/api/register", status_code=201)
def register(body: RegisterIn, request: Request):
    name = body.name.strip()
    if not name:
        fail(400, "need_name")
    email = clean_email(body.email)
    if len(body.password) < MIN_PASSWORD:
        fail(400, "short_password")
    if body.trainer_code and body.trainer_code.strip() and not valid_trainer_code(body.trainer_code):
        fail(403, "wrong_code")
    role = role_for(email, body.trainer_code)
    if role == "student":
        check_class_code(body.class_code)
    if supa.enabled():
        return supabase_register(body, name, email, request)
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
    if supa.enabled():
        try:
            token = supa.sign_in(email, body.password)
        except supa.SupabaseError as err:
            if err.code == "invalid":
                _failed.setdefault(email, []).append(datetime.now(timezone.utc).timestamp())
            supabase_fail(err)
        _failed.pop(email, None)
        return supabase_account(supabase_user(token))
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


# ---------------------------------------------------------------------------
# Supabase Auth (dacă sunt setate SUPABASE_URL și SUPABASE_ANON_KEY): parolele,
# confirmarea emailului, resetarea și Google merg prin Supabase. Orice token
# primit din browser îl verificăm la Supabase înainte să deschidem o sesiune.
# ---------------------------------------------------------------------------

RECOVER_LIMIT = 3  # emailuri de resetare per adresă, la 10 minute
_recover_sent: dict[str, list] = {}


class SupabaseTokenIn(BaseModel):
    access_token: str = Field(min_length=10, max_length=5000)
    class_code: Optional[str] = Field(None, max_length=100)


class RecoverIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)


class NewPasswordIn(BaseModel):
    access_token: str = Field(min_length=10, max_length=5000)
    password: str = Field(max_length=200)


def app_url(request: Request) -> str:
    """Unde ne întoarce linkul din email (trebuie adăugat și în Supabase → Redirect URLs)."""
    return str(request.base_url).rstrip("/") + "/static/index.html"


def supabase_fail(err: "supa.SupabaseError"):
    key = {"invalid": "wrong_login", "unconfirmed": "confirm_email_first", "exists": "email_taken",
           "weak": "weak_password"}.get(err.code, "auth_down")
    fail({"wrong_login": 401, "confirm_email_first": 403, "email_taken": 409, "weak_password": 400}.get(key, 503), key)


def supabase_user(token: str) -> dict:
    try:
        return supa.get_user(token)
    except supa.SupabaseError as err:
        if err.code == "invalid":
            fail(401, "link_expired")
        supabase_fail(err)


def supabase_account(sb_user: dict, class_code: Optional[str] = None) -> dict:
    """Leagă contul Supabase de contul nostru (același email = aceleași date) și deschide sesiunea."""
    email = clean_email(sb_user["email"])
    provider = supa.provider(sb_user)
    # TRAINER_EMAILS contează doar dacă emailul e dovedit (Google sau confirmare pe email);
    # altfel oricine și-ar putea face cont cu emailul trainerului
    trusted = provider == "google" or supa.emails_are_verified()
    with _lock:
        user = db["users"].get(email)
        pending = db.setdefault("supabase_pending", {}).get(email)
        if user is None:
            role = "trainer" if (pending or {}).get("role") == "trainer" or (trusted and email in TRAINER_EMAILS) else "student"
            if role == "student" and not (pending or {}).get("class_ok"):
                check_class_code(class_code)
            name = (pending or {}).get("name") or supa.display_name(sb_user)
            user = db["users"][email] = {"name": name, "email": email, "role": role, "created_at": now()}
        elif user["role"] == "student" and trusted and email in TRAINER_EMAILS:
            user["role"] = "trainer"
        db["supabase_pending"].pop(email, None)
        user["supabase"] = "email" if provider == "email" else provider
        return start_session(user)


def supabase_register(body: RegisterIn, name: str, email: str, request: Request) -> dict:
    # Ce am verificat aici (codul clasei, codul de trainer) ținem minte până la confirmarea emailului
    with _lock:
        pending = db.setdefault("supabase_pending", {})
        week_ago = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() - 7 * 86400, timezone.utc).isoformat(timespec="seconds")
        for old in [e for e, p in pending.items() if p.get("at", "") < week_ago]:
            pending.pop(old)
        is_trainer = valid_trainer_code(body.trainer_code)
        pending[email] = {
            "name": name, "role": "trainer" if is_trainer else "student",
            "class_ok": is_trainer or not CLASS_CODE or same((body.class_code or "").strip(), CLASS_CODE),
            "at": now()}
        save_db()
    try:
        token = supa.sign_up(email, body.password, name, app_url(request))
    except supa.SupabaseError as err:
        if err.code != "exists":
            supabase_fail(err)
        # Contul există deja la Supabase (de exemplu creat din alt loc): încercăm să intrăm cu parola dată
        try:
            token = supa.sign_in(email, body.password)
        except supa.SupabaseError as err2:
            supabase_fail(supa.SupabaseError("exists" if err2.code == "invalid" else err2.code))
    if not token:
        return {"confirm_email": True, "email": email}
    return supabase_account(supabase_user(token), body.class_code)


@app.post("/api/auth/supabase")
def supabase_login(body: SupabaseTokenIn):
    """Întoarcerea din linkul de confirmare sau de la Google (prin Supabase)."""
    if not supa.enabled():
        fail(404, "supabase_off")
    return supabase_account(supabase_user(body.access_token), body.class_code)


@app.post("/api/auth/supabase/recover")
def supabase_recover(body: RecoverIn, request: Request):
    """Trimite linkul de resetare. Răspundem la fel dacă emailul are cont sau nu."""
    if not supa.enabled():
        fail(404, "supabase_off")
    email = clean_email(body.email)
    cutoff = datetime.now(timezone.utc).timestamp() - LOCK_SECONDS
    sent = [t for t in _recover_sent.get(email, []) if t > cutoff]
    if len(sent) >= RECOVER_LIMIT:
        fail(429, "too_many_attempts")
    _recover_sent[email] = sent + [datetime.now(timezone.utc).timestamp()]
    try:
        supa.recover(email, app_url(request))
    except supa.SupabaseError as err:
        supabase_fail(err)
    return {"ok": True}


@app.post("/api/auth/supabase/new-password")
def supabase_new_password(body: NewPasswordIn):
    """Parola nouă, din linkul de resetare primit pe email; apoi intri direct."""
    if not supa.enabled():
        fail(404, "supabase_off")
    if len(body.password) < MIN_PASSWORD:
        fail(400, "short_password")
    sb_user = supabase_user(body.access_token)
    try:
        supa.update_password(body.access_token, body.password)
    except supa.SupabaseError as err:
        supabase_fail(err)
    account = supabase_account(sb_user)
    with _lock:
        db["users"][clean_email(sb_user["email"])]["supabase"] = "email"  # acum are și parolă
        save_db()
    return account


class PasswordIn(BaseModel):
    current: Optional[str] = Field(None, max_length=200)
    new: str = Field(max_length=200)


@app.post("/api/me/password")
def change_password(body: PasswordIn, user: dict = Depends(current_user)):
    """Schimbă parola. Conturile create cu Google își pot pune o parolă fără cea veche."""
    account = db["users"].get(user["key"])
    if account is None:
        fail(401, "login_again")
    if supa.enabled():
        # Parola stă la Supabase: o schimbăm cu un token obținut din parola actuală
        if len(body.new) < MIN_PASSWORD:
            fail(400, "short_password")
        throttle(account["email"])
        try:
            token = supa.sign_in(account["email"], body.current or "")
        except supa.SupabaseError as err:
            if err.code == "invalid":
                _failed.setdefault(account["email"], []).append(datetime.now(timezone.utc).timestamp())
                fail(403, "wrong_current")
            supabase_fail(err)
        try:
            supa.update_password(token, body.new)
        except supa.SupabaseError as err:
            supabase_fail(err)
        return {"ok": True}
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
    temporary_password: Optional[str] = None
    email_sent: bool = False


@app.post("/api/students/{student_key}/reset-password")
def reset_password(student_key: str, request: Request, user: dict = Depends(require_trainer)) -> ResetOut:
    """Trainerul generează o parolă temporară pentru un student care a uitat-o.
    Cu Supabase, studentul primește în schimb un link de resetare pe email."""
    if student_key not in known_students():
        fail(404, "no_student")
    if supa.enabled():
        try:
            supa.recover(student_key, app_url(request))
        except supa.SupabaseError as err:
            supabase_fail(err)
        return ResetOut(email_sent=True)
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
            "has_password": account.get("supabase") == "email" if supa.enabled() else bool(account.get("hash")), "prefs": db["prefs"].get(user["key"], {})}


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
    # Adresa Supabase e publică (o vede oricum browserul la Google); anon key rămâne pe server
    sb = {"url": supa.url(), "google": supa.google_enabled()} if supa.enabled() else None
    return {"ai": ai.available(), "topics": TOPICS, "google_client_id": None if sb else (GOOGLE_CLIENT_ID or None),
            "class_code_required": bool(CLASS_CODE), "supabase": sb}


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


# ---------------------------------------------------------------------------
# Byte, robotul de știri: o dată la 24 de ore face „Briefing-ul zilei” din
# toate sursele. Rulează pe server, într-un fir separat; cheia API nu iese
# de aici. Fiecare limbă se scrie o singură dată pe zi (apoi stă în db).
# ---------------------------------------------------------------------------

DIGEST_LANGS = [l for l in os.environ.get("CUTIA_DIGEST_LANGS", "ro,en").split(",") if l in ai.LANGS]
AI_RETRY_SECONDS = 30 * 60
_digest_state = {"running": False, "manual_at": 0.0, "auto_at": 0.0}
_digest_write_lock = threading.Lock()


def make_digest(fetcher=None) -> dict:
    items, errors = news.collect(fetcher, limit=digest.SCAN_LIMIT)
    d = digest.build(items, len(news.feeds()), errors)
    with _lock:
        kept = [x for x in db.setdefault("digests", []) if x["date"] != d["date"]] + [d]
        db["digests"] = sorted(kept, key=lambda x: x["date"])[-digest.KEEP_DAYS:]
        save_db()
    for lang in DIGEST_LANGS:
        digest_view(d, lang)
    return d


def run_digest_in_background():
    def job():
        try:
            make_digest()
        except Exception:  # o sursă sau AI-ul căzut nu oprește serverul; încercăm la următorul tur
            pass
        finally:
            _digest_state["running"] = False
    if not _digest_state["running"]:
        _digest_state["running"] = True
        threading.Thread(target=job, daemon=True).start()


def digest_view(d: dict, lang: str) -> dict:
    """Briefing-ul în limba cerută: scris de Claude (o dată) sau varianta locală."""
    import time
    with _digest_write_lock:  # mai mulți colegi deodată = tot un singur apel la Claude
        view = d["by_lang"].get(lang)
        failed_at = d.setdefault("failed", {}).get(lang, 0)
        if view is None and ai.available() and time.time() - failed_at > AI_RETRY_SECONDS:
            view = digest.write(d, lang, ai)
            with _lock:
                if view:
                    d["by_lang"][lang] = view
                else:
                    d["failed"][lang] = time.time()
                save_db()
    return view or digest.local_view(d)


def digest_loop():
    import time
    while True:
        if digest.due(db.get("digests", [])) and not _digest_state["running"]:
            run_digest_in_background()
        time.sleep(600)


def start_byte():
    if os.environ.get("CUTIA_DIGEST", "on") != "off":
        threading.Thread(target=digest_loop, daemon=True).start()


@app.get("/api/digest")
def get_digest(date: Optional[str] = None, user: dict = Depends(current_user)):
    digests = db.get("digests", [])
    d = next((x for x in digests if x["date"] == date), None) if date else (digests[-1] if digests else None)
    import time
    # Primul briefing (sau cel de azi) se face acum; dacă sursele nu merg, nu reîncercăm la fiecare vizită
    if (d is None or (not date and digest.due(digests))) and time.time() - _digest_state["auto_at"] > 600:
        _digest_state["auto_at"] = time.time()
        run_digest_in_background()
    base = {"next_run": digest.next_run(), "generating": _digest_state["running"],
            "history": [x["date"] for x in reversed(digests)], "hour": digest.HOUR}
    if d is None:
        return {**base, "digest": None}
    view = digest_view(d, current_lang.get())
    return {**base, "digest": {"date": d["date"], "created_at": d["created_at"], "window_hours": d["window_hours"],
                               "stats": d["stats"], **view}}


@app.post("/api/digest/run")
def rerun_digest(user: dict = Depends(require_trainer)):
    """Trainerul cere un briefing nou acum (cel mult o dată la 10 minute)."""
    import time
    if time.time() - _digest_state["manual_at"] > 600:
        _digest_state["manual_at"] = time.time()
        run_digest_in_background()
    return {"generating": _digest_state["running"]}


# ---------------------------------------------------------------------------
# Atelier (🔒 privat): unelte pentru student. „Verifică repo-ul” citește un
# repo public de pe GitHub și verifică lista „Gata când” a trainerului.
# ---------------------------------------------------------------------------

_cooldowns: dict = {}


def cooldown(user: dict, action: str, seconds: int):
    """Limită simplă per utilizator, ca să nu consumăm GitHub/AI-ul cu click-uri repetate."""
    import time
    key = (user["key"], action)
    wait = int(_cooldowns.get(key, 0) + seconds - time.time())
    if wait > 0:
        fail(429, "slow_down", wait)
    _cooldowns[key] = time.time()


class RepoCheckIn(BaseModel):
    url: str = Field(min_length=10, max_length=300)


@app.post("/api/repo-check")
def repo_check(body: RepoCheckIn, user: dict = Depends(current_user)):
    try:
        repocheck.parse_url(body.url)
    except repocheck.RepoError:
        fail(400, "not_github")
    cooldown(user, "repo", 15)
    try:
        return repocheck.check(body.url)
    except repocheck.RepoError as err:
        fail({"not_github": 400, "not_found": 404, "github_busy": 429}.get(err.code, 502),
             {"not_found": "repo_not_found"}.get(err.code, err.code))


# ---------------------------------------------------------------- Error Doctor (privat)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
DOCTOR_KEEP = 20


def image_type(data: bytes) -> Optional[str]:
    """Tipul imaginii după primii octeți (nu după nume): PNG, JPEG sau WebP."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def read_image(upload: Optional[UploadFile]):
    if upload is None or not upload.filename:
        return None
    data = upload.file.read(MAX_IMAGE_BYTES + 1)
    kind = image_type(data)
    if len(data) > MAX_IMAGE_BYTES or not kind:
        fail(400, "bad_image")
    return kind, data


def doctor_view(e: dict) -> dict:
    return {k: e[k] for k in ("id", "created_at", "excerpt", "had_key", "ai", "result", "local", "image")}


@app.post("/api/doctor", status_code=201)
def doctor(text: str = Form("", max_length=8000), image: Optional[UploadFile] = File(None), user: dict = Depends(current_user)):
    text = text.strip()
    img = read_image(image)
    if not text and not img:
        fail(400, "need_error")
    cooldown(user, "doctor", 8)
    # Cheile lipite din greșeală nu ajung nici la Claude, nici în baza de date
    clean, had_key = tools.redact(text)
    result = tools.diagnose(clean, img, current_lang.get()) if ai.available() else None
    entry = {"id": next_id(), "author_key": user["key"], "created_at": now(), "excerpt": clean[:400], "had_key": had_key,
             "ai": bool(result), "result": result, "local": None if result else tools.local_match(clean), "image": bool(img)}
    with _lock:
        mine = [e for e in db.setdefault("doctor", []) if e["author_key"] == user["key"]]
        drop = {e["id"] for e in mine[:-(DOCTOR_KEEP - 1)]} if len(mine) >= DOCTOR_KEEP else set()
        db["doctor"] = [e for e in db["doctor"] if e["id"] not in drop] + [entry]
        save_db()
    return doctor_view(entry)


@app.get("/api/doctor")
def doctor_history(user: dict = Depends(current_user)):
    return [doctor_view(e) for e in reversed(db.get("doctor", [])) if e["author_key"] == user["key"]]


@app.delete("/api/doctor/{entry_id}")
def doctor_delete(entry_id: int, user: dict = Depends(current_user)):
    with _lock:
        before = len(db.get("doctor", []))
        db["doctor"] = [e for e in db.get("doctor", []) if not (e["id"] == entry_id and e["author_key"] == user["key"])]
        if len(db["doctor"]) == before:
            fail(404, "no_item")
        save_db()
    return {"ok": True}


# ---------------------------------------------------------------- Prompt Lab + Hall of Prompts (public)

class PromptIn(BaseModel):
    prompt: str = Field(min_length=5, max_length=6000)


@app.post("/api/prompt-lab")
def prompt_lab(body: PromptIn, user: dict = Depends(current_user)):
    cooldown(user, "prompt", 5)
    clean, had_key = tools.redact(body.prompt.strip())
    result = tools.lab(clean, current_lang.get()) if ai.available() else tools.score_local(clean)
    return {**result, "had_key": had_key}


class HallIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=10, max_length=3000)
    note: str = Field("", max_length=300)


MAX_HALL_PER_USER = 30


def hall_view(h: dict, user: dict) -> dict:
    return {"id": h["id"], "title": h["title"], "prompt": h["prompt"], "note": h["note"], "author": h["author"],
            "created_at": h["created_at"], "likes": len(h["likes"]), "liked": user["key"] in h["likes"],
            "mine": h["author_key"] == user["key"]}


@app.get("/api/hall")
def hall_list(user: dict = Depends(current_user)):
    items = sorted(db.get("hall", []), key=lambda h: (len(h["likes"]), h["created_at"]), reverse=True)
    return [hall_view(h, user) for h in items]


@app.post("/api/hall", status_code=201)
def hall_add(body: HallIn, user: dict = Depends(current_user)):
    prompt, _ = tools.redact(body.prompt.strip())
    with _lock:
        if sum(h["author_key"] == user["key"] for h in db.setdefault("hall", [])) >= MAX_HALL_PER_USER:
            fail(400, "too_many_posts", MAX_HALL_PER_USER)
        h = {"id": next_id(), "author_key": user["key"], "author": user["name"], "title": body.title.strip(), "prompt": prompt,
             "note": body.note.strip(), "likes": [], "created_at": now()}
        db["hall"].append(h)
        save_db()
    return hall_view(h, user)


def find_hall(item_id: int) -> dict:
    h = next((x for x in db.get("hall", []) if x["id"] == item_id), None)
    if h is None:
        fail(404, "no_item")
    return h


@app.post("/api/hall/{item_id}/like")
def hall_like(item_id: int, user: dict = Depends(current_user)):
    with _lock:
        h = find_hall(item_id)
        if h["author_key"] == user["key"]:
            fail(400, "own_like")
        if user["key"] in h["likes"]:
            h["likes"].remove(user["key"])
        else:
            h["likes"].append(user["key"])
        save_db()
    return hall_view(h, user)


@app.delete("/api/hall/{item_id}")
def hall_delete(item_id: int, user: dict = Depends(current_user)):
    with _lock:
        h = find_hall(item_id)
        if h["author_key"] != user["key"] and user["role"] != "trainer":
            fail(403, "not_author")
        db["hall"].remove(h)
        save_db()
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
