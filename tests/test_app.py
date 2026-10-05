import os
import tempfile

os.environ["CUTIA_PERSIST"] = "0"
os.environ["CUTIA_AI"] = "off"
os.environ["TRAINER_CODE"] = "secret"
os.environ["TRAINER_EMAILS"] = "radu@test.ro"
os.environ.pop("CLASS_CODE", None)
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ["CUTIA_UPLOADS"] = tempfile.mkdtemp()

import pytest
from fastapi.testclient import TestClient

from src import app as app_module

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def reset_db():
    app_module.db.update({
        "users": {}, "sessions": {}, "prefs": {}, "drafts": [], "questions": [], "proposals": [], "submissions": [],
        "messages": [], "assignments": [], "announcements": [], "bonuses": [], "next_id": 1,
    })
    app_module._failed.clear()


def email_for(name):
    return f"{name.lower().replace(' ', '.')}@test.ro"


def login(name, role="student", code=None, password="parola-test"):
    """Creează contul la prima folosire (Radu = trainer, din TRAINER_EMAILS), apoi intră."""
    email = email_for(name)
    if email not in app_module.db["users"]:
        r = client.post("/api/register", json={"name": name, "email": email, "password": password})
    else:
        r = client.post("/api/login", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.text
    assert r.json()["role"] == role
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_trainer_is_recognized_by_email_or_code():
    assert login("Radu", "trainer") is not None
    r = client.post("/api/register", json={"name": "T", "email": "t@x.ro", "password": "parola-buna", "trainer_code": "gresit"})
    assert r.status_code == 403
    r = client.post("/api/register", json={"name": "T", "email": "t@x.ro", "password": "parola-buna", "trainer_code": "secret"})
    assert r.json()["role"] == "trainer"
    r = client.post("/api/register", json={"name": "S", "email": "s@x.ro", "password": "parola-buna"})
    assert r.json()["role"] == "student"


def test_register_validation_and_duplicates():
    base = {"name": "Ana", "email": "ana@test.ro", "password": "parola-buna"}
    assert client.post("/api/register", json={**base, "email": "nu-e-email"}).status_code == 400
    assert client.post("/api/register", json={**base, "password": "scurta"}).status_code == 400
    assert client.post("/api/register", json=base).status_code == 201
    assert client.post("/api/register", json={**base, "email": "ANA@test.ro "}).status_code == 409
    assert client.post("/api/login", json={"email": "Ana@Test.ro", "password": "parola-buna"}).status_code == 200


def test_class_code_required_when_set(monkeypatch):
    monkeypatch.setattr(app_module, "CLASS_CODE", "VIBE2026")
    base = {"name": "Ana", "email": "ana@test.ro", "password": "parola-buna"}
    assert client.post("/api/register", json=base).status_code == 403
    assert client.post("/api/register", json={**base, "class_code": "VIBE2026"}).status_code == 201
    # Trainerul (din TRAINER_EMAILS) nu are nevoie de codul clasei
    assert client.post("/api/register", json={"name": "Radu", "email": "radu@test.ro", "password": "parola-buna"}).status_code == 201
    assert client.get("/api/config").json()["class_code_required"] is True


def test_login_lockout_after_failed_attempts():
    login("Ana")
    for _ in range(5):
        assert client.post("/api/login", json={"email": "ana@test.ro", "password": "gresit!!"}).status_code == 401
    r = client.post("/api/login", json={"email": "ana@test.ro", "password": "parola-test"})
    assert r.status_code == 429


def test_wrong_email_and_wrong_password_look_the_same():
    login("Ana")
    a = client.post("/api/login", json={"email": "nimeni@test.ro", "password": "orice-parola"}).json()
    b = client.post("/api/login", json={"email": "ana@test.ro", "password": "orice-parola"}).json()
    assert a == b


def test_google_login_disabled_without_client_id():
    assert client.post("/api/auth/google", json={"credential": "x" * 20}).status_code == 404


def test_google_login_creates_account(monkeypatch):
    from google.oauth2 import id_token
    monkeypatch.setattr(app_module, "GOOGLE_CLIENT_ID", "client-123")
    monkeypatch.setattr(id_token, "verify_oauth2_token",
                        lambda tok, req, aud: {"email": "Madalina@Gmail.com", "email_verified": True, "name": "Madalina"})
    r = client.post("/api/auth/google", json={"credential": "x" * 20})
    assert r.status_code == 200 and r.json()["name"] == "Madalina" and r.json()["role"] == "student"
    assert "madalina@gmail.com" in app_module.db["users"]
    monkeypatch.setattr(id_token, "verify_oauth2_token",
                        lambda tok, req, aud: {"email": "x@gmail.com", "email_verified": False})
    assert client.post("/api/auth/google", json={"credential": "x" * 20}).status_code == 401


def test_trainer_can_reset_a_student_password():
    ana = login("Ana")
    trainer = login("Radu", "trainer")
    assert client.post("/api/students/ana@test.ro/reset-password", headers=ana).status_code == 403
    temp = client.post("/api/students/ana@test.ro/reset-password", headers=trainer).json()["temporary_password"]
    assert client.get("/api/me", headers=ana).status_code == 401  # sesiunea veche s-a închis
    assert client.post("/api/login", json={"email": "ana@test.ro", "password": temp}).status_code == 200


def test_questions_visible_only_to_author_and_trainer():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer")

    r = client.post("/api/questions", json={"text": "Ce e un API?"}, headers=ana)
    assert r.status_code == 201
    qid = r.json()["id"]

    assert len(client.get("/api/questions", headers=ana).json()) == 1
    assert client.get("/api/questions", headers=bob).json() == []
    assert len(client.get("/api/questions", headers=trainer).json()) == 1

    # Doar trainerul răspunde
    assert client.post(f"/api/questions/{qid}/answer", json={"text": "x"}, headers=bob).status_code == 403
    r = client.post(f"/api/questions/{qid}/answer", json={"text": "O interfață."}, headers=trainer)
    assert r.status_code == 200
    assert client.get("/api/questions", headers=ana).json()[0]["answer"] == "O interfață."


def test_anonymous_question_hides_name_from_trainer():
    ana = login("Ana")
    trainer = login("Radu", "trainer")
    client.post("/api/questions", json={"text": "Întrebare", "anonymous": True}, headers=ana)
    q = client.get("/api/questions", headers=trainer).json()[0]
    assert q["author"] == "Anonim"
    assert "author_key" not in q


def test_refine_asks_only_for_missing_fields():
    ana = login("Ana")
    r = client.post("/api/proposals/refine", json={
        "title": "  calendarul clasei ",
        "description": "arata   termenele temelor si orele de curs intr-un singur loc",
        "audience": "",
    }, headers=ana)
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Calendarul clasei"
    assert data["description"].endswith(".")
    assert [m["field"] for m in data["missing"]] == ["audience"]


def test_submit_requires_approval_and_fields():
    ana = login("Ana")
    body = {"title": "Calendar", "description": "Arată termenele.", "audience": "Studenții"}
    assert client.post("/api/proposals", json=body, headers=ana).status_code == 400
    assert client.post("/api/proposals", json={**body, "audience": "", "approved": True}, headers=ana).status_code == 400
    assert client.post("/api/proposals", json={**body, "approved": True}, headers=ana).status_code == 201


def test_trainer_chooses_and_students_vote():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer")
    body = {"title": "Calendar", "description": "Arată termenele.", "audience": "Studenții", "approved": True}
    pid = client.post("/api/proposals", json=body, headers=ana).json()["id"]

    assert client.post(f"/api/proposals/{pid}/choose", headers=ana).status_code == 403
    assert client.post(f"/api/proposals/{pid}/choose", headers=trainer).json()["chosen"] is True

    assert client.post(f"/api/proposals/{pid}/vote", headers=bob).json()["votes"] == 1
    assert client.post(f"/api/proposals/{pid}/vote", headers=bob).json()["votes"] == 0
    assert client.post(f"/api/proposals/{pid}/vote", headers=trainer).status_code == 403

    listed = client.get("/api/proposals", headers=trainer).json()
    assert listed[0]["chosen"] is True and "voters" not in listed[0]


def test_requires_login():
    assert client.get("/api/questions").status_code == 401


def test_student_b_cannot_log_in_as_student_a():
    ana = login("Ana", password="parola-ana1")
    client.post("/api/questions", json={"text": "Întrebarea Anei"}, headers=ana)

    # Studentul B încearcă să intre pe contul Anei
    r = client.post("/api/login", json={"email": "ana@test.ro", "password": "ghicit123"})
    assert r.status_code == 401

    bob = login("Bob", password="parola-bob1")
    assert client.get("/api/questions", headers=bob).json() == []
    assert len(client.get("/api/questions", headers=login("Ana", password="parola-ana1")).json()) == 1


def test_password_required_and_not_exposed():
    r = client.post("/api/register", json={"name": "Ana", "email": "ana@test.ro", "password": "123"})
    assert r.status_code == 400
    login("Ana")
    assert "parola-test" not in str(app_module.db["users"])


def test_api_key_is_never_sent_to_browser():
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-secret"
    try:
        for path in ("/static/index.html", "/static/app.js"):
            assert "sk-ant" not in client.get(path).text
        ana = login("Ana")
        r = client.post("/api/proposals/refine", json={"title": "x"}, headers=ana)
        assert "sk-ant" not in r.text
    finally:
        del os.environ["ANTHROPIC_API_KEY"]


def test_refine_asks_at_most_three_questions_and_explains():
    ana = login("Ana")
    data = client.post("/api/proposals/refine", json={"title": "x"}, headers=ana).json()
    assert len(data["missing"]) <= 3
    assert "understood" in data


def test_config_lists_vibe_coding_topics():
    data = client.get("/api/config").json()
    assert data["ai"] is False
    assert {"prompting", "security", "claude-code", "deploy"} <= set(data["topics"])


def test_question_topic_falls_back_to_other():
    ana = login("Ana")
    q = client.post("/api/questions", json={"text": "Ceva?", "category": "nu-exista"}, headers=ana).json()
    assert q["category"] == "other"
    q = client.post("/api/questions", json={"text": "Ceva?", "category": "prompting"}, headers=ana).json()
    assert q["category"] == "prompting"


def test_ai_answer_only_for_own_question_and_needs_ai():
    ana, bob = login("Ana"), login("Bob")
    qid = client.post("/api/questions", json={"text": "Ce e un prompt?"}, headers=ana).json()["id"]
    assert client.post(f"/api/questions/{qid}/ai-answer", headers=bob).status_code == 403
    r = client.post(f"/api/questions/{qid}/ai-answer", headers=ana)
    assert r.status_code == 503  # AI oprit în teste: fără cheie, fără apel


def test_ai_answer_is_stored_once(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.ai, "available", lambda: True)
    monkeypatch.setattr(app_module.ai, "answer_question",
                        lambda text, topic, lang: calls.append(lang) or "Încearcă așa.")
    ana = login("Ana")
    qid = client.post("/api/questions", json={"text": "Ce e un prompt?"}, headers=ana).json()["id"]
    for _ in range(2):
        r = client.post(f"/api/questions/{qid}/ai-answer", headers={**ana, "X-Lang": "en"})
        assert r.json()["ai_answer"] == "Încearcă așa."
    assert calls == ["en"]


def test_errors_follow_selected_language():
    bad = {"email": "nimeni@test.ro", "password": "orice-parola"}
    assert client.post("/api/login", json=bad, headers={"X-Lang": "en"}).json()["detail"] == "Wrong email or password."
    assert client.post("/api/login", json=bad).json()["detail"] == "Email sau parolă greșită."


def test_local_refine_in_english():
    ana = login("Ana")
    r = client.post("/api/proposals/refine", json={"title": "quiz"}, headers={**ana, "X-Lang": "en"}).json()
    assert r["missing"][0]["question"].startswith("Briefly describe")


# ---------------------------------------------------------------- teme & proiecte

def submit(headers, files=None, **data):
    form = {"kind": "homework", "title": "Tema 1", **data}
    return client.post("/api/submissions", data=form, files=files or [], headers=headers)


def test_submission_private_to_author_and_trainer():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer")
    r = submit(ana, files=[("files", ("tema.md", b"# Tema mea", "text/markdown"))],
               link="https://github.com/ana/cutia-clasei-ana", checklist=["no_keys", "nope"])
    assert r.status_code == 201, r.text
    sub = r.json()
    assert sub["checklist"] == ["no_keys"]
    assert "stored" not in sub["files"][0]
    fid = sub["files"][0]["id"]

    assert client.get("/api/submissions", headers=bob).json() == []
    assert len(client.get("/api/submissions", headers=trainer).json()) == 1
    # B nu poate descărca fișierul lui A
    assert client.get(f"/api/submissions/{sub['id']}/files/{fid}", headers=bob).status_code == 404
    d = client.get(f"/api/submissions/{sub['id']}/files/{fid}", headers=trainer)
    assert d.status_code == 200 and d.content == b"# Tema mea"
    assert d.headers["content-type"] == "application/octet-stream"
    assert "attachment" in d.headers["content-disposition"]


def test_submission_validation():
    ana = login("Ana")
    assert submit(ana, title="").status_code == 400
    assert submit(ana, link="javascript:alert(1)").status_code == 400
    assert submit(ana).status_code == 400  # nimic de predat
    bad = submit(ana, files=[("files", ("virus.exe", b"x", "application/octet-stream"))])
    assert bad.status_code == 400
    big = submit(ana, files=[("files", ("mare.pdf", b"x" * (10 * 1024 * 1024 + 1), "application/pdf"))])
    assert big.status_code == 400
    many = submit(ana, files=[("files", (f"f{i}.txt", b"x", "text/plain")) for i in range(6)])
    assert many.status_code == 400


def test_trainer_reviews_submission():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer")
    sid = submit(ana, note="Am terminat!").json()["id"]
    body = {"status": "reviewed", "feedback": "Super, adaugă README."}
    assert client.post(f"/api/submissions/{sid}/review", json=body, headers=bob).status_code == 403
    r = client.post(f"/api/submissions/{sid}/review", json=body, headers=trainer)
    assert r.json()["status"] == "reviewed"
    assert client.get("/api/submissions", headers=ana).json()[0]["feedback"] == "Super, adaugă README."


# ---------------------------------------------------------------- sesiuni & preferințe

def test_session_survives_restart_and_logout_ends_it():
    ana = login("Ana")
    token = ana["Authorization"].split()[1]
    assert token not in str(app_module.db["sessions"])  # se salvează doar hash-ul
    assert client.get("/api/me", headers=ana).json()["name"] == "Ana"
    client.post("/api/logout", headers=ana)
    assert client.get("/api/me", headers=ana).status_code == 401


def test_prefs_are_saved():
    ana = login("Ana")
    r = client.patch("/api/me", json={"lang": "fr", "hide_from_leaderboard": True}, headers=ana)
    assert r.json()["prefs"] == {"lang": "fr", "hide_from_leaderboard": True}
    assert client.patch("/api/me", json={"lang": "xx"}, headers=ana).json()["prefs"]["lang"] == "fr"


def test_errors_in_french():
    r = client.post("/api/login", json={"email": "nimeni@test.ro", "password": "orice-parola"}, headers={"X-Lang": "fr"})
    assert r.json()["detail"] == "E-mail ou mot de passe incorrect."


# ---------------------------------------------------------------- mesaje directe

def test_direct_messages_are_private():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer")
    client.post("/api/dm", json={"text": "Bună! Am o întrebare despre temă."}, headers=ana)
    assert client.get("/api/dm", headers=bob).json()["messages"] == []
    assert client.get("/api/dm/ana@test.ro", headers=bob).status_code == 403
    assert client.get("/api/dm/unread", headers=trainer).json()["unread"] == 1

    threads = client.get("/api/dm", headers=trainer).json()["threads"]
    ana_thread = next(t for t in threads if t["student_key"] == "ana@test.ro")
    assert ana_thread["unread"] == 1
    assert len(client.get("/api/dm/ana@test.ro", headers=trainer).json()["messages"]) == 1
    assert client.get("/api/dm/unread", headers=trainer).json()["unread"] == 0  # citit

    client.post("/api/dm/ana@test.ro", json={"text": "Sigur, spune!"}, headers=trainer)
    assert client.get("/api/dm/unread", headers=ana).json()["unread"] == 1
    msgs = client.get("/api/dm", headers=ana).json()["messages"]
    assert [m["from_role"] for m in msgs] == ["student", "trainer"]
    assert client.get("/api/dm/unread", headers=ana).json()["unread"] == 0
    assert client.post("/api/dm/nimeni", json={"text": "x"}, headers=trainer).status_code == 404


# ---------------------------------------------------------------- puncte

def test_points_follow_the_rules():
    ana, bob, cris = login("Ana"), login("Bob"), login("Cris")
    trainer = login("Radu", "trainer")
    a = client.post("/api/assignments", json={"title": "Tema 1", "due_at": "2999-01-01T00:00:00Z", "points": 25},
                    headers=trainer).json()
    sid = submit(ana, note="gata", assignment_id=str(a["id"])).json()["id"]
    submit(ana, note="din nou", assignment_id=str(a["id"]))           # a doua predare la aceeași temă nu mai punctează
    client.post(f"/api/submissions/{sid}/review", json={"status": "reviewed"}, headers=trainer)
    pid = client.post("/api/proposals", json={"title": "Quiz", "description": "Un quiz.", "audience": "Clasa",
                                              "approved": True}, headers=ana).json()["id"]
    assert client.post(f"/api/proposals/{pid}/vote", headers=ana).status_code == 400  # nu-ți votezi ideea
    client.post(f"/api/proposals/{pid}/vote", headers=bob)
    client.post(f"/api/proposals/{pid}/vote", headers=cris)
    client.post(f"/api/proposals/{pid}/choose", headers=trainer)
    for i in range(5):
        client.post("/api/questions", json={"text": f"Întrebarea {i}?"}, headers=ana)
    client.post("/api/points/bonus", json={"student_key": "ana@test.ro", "points": 7, "reason": "Ajutor colegilor"},
                headers=trainer)

    me = client.get("/api/points/me", headers=ana).json()
    # 10 predare + 5 la timp + 25 revizuit + 5 idee + 4 voturi + 30 aleasă + 6 întrebări (max 3/zi) + 7 bonus
    assert me["total"] == 92
    assert me["level"]["key"] == "apprentice"
    assert {"first_homework", "first_idea", "chosen", "first_question"} <= set(me["badges"])


def test_bonus_rules_and_access():
    ana = login("Ana")
    trainer = login("Radu", "trainer")
    body = {"student_key": "ana@test.ro", "points": 10, "reason": "x"}
    assert client.post("/api/points/bonus", json=body, headers=ana).status_code == 403
    assert client.post("/api/points/bonus", json={**body, "points": 0}, headers=trainer).status_code == 400
    assert client.post("/api/points/bonus", json={**body, "reason": " "}, headers=trainer).status_code == 400
    assert client.post("/api/points/bonus", json={**body, "student_key": "zz"}, headers=trainer).status_code == 404
    assert client.get("/api/points/ana@test.ro", headers=ana).status_code == 403


def test_leaderboard_respects_hide():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer")
    client.patch("/api/me", json={"hide_from_leaderboard": True}, headers=ana)
    names_bob = [r["name"] for r in client.get("/api/leaderboard", headers=bob).json()]
    assert "Ana" not in names_bob and "Bob" in names_bob
    assert any(r["me"] for r in client.get("/api/leaderboard", headers=ana).json())  # se vede pe sine
    assert "Ana" in [r["name"] for r in client.get("/api/leaderboard", headers=trainer).json()]
    assert "key" not in client.get("/api/leaderboard", headers=bob).json()[0]


# ---------------------------------------------------------------- teme & anunțuri

def test_assignments_and_announcements():
    ana = login("Ana")
    trainer = login("Radu", "trainer")
    assert client.post("/api/assignments", json={"title": "T"}, headers=ana).status_code == 403
    a = client.post("/api/assignments", json={"title": "Tema 2", "due_at": "2030-05-01T18:00"}, headers=trainer).json()
    assert a["due_at"] == "2030-05-01T18:00:00+00:00"
    assert client.get("/api/assignments", headers=ana).json()[0]["submitted"] is False
    submit(ana, note="x", assignment_id=str(a["id"]))
    assert client.get("/api/assignments", headers=ana).json()[0]["submitted"] is True
    assert submit(ana, note="x", assignment_id="9999").status_code == 404

    client.post("/api/announcements", json={"text": "Ora de joi începe la 18:30", "pinned": True}, headers=trainer)
    assert client.get("/api/announcements", headers=ana).json()[0]["pinned"] is True
    assert client.post("/api/announcements", json={"text": "x"}, headers=ana).status_code == 403


# ---------------------------------------------------------------- AI News

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Startup launches new AI coding agent for beginners</title><link>https://example.com/agent</link>
<description>&lt;p&gt;A free &lt;b&gt;app&lt;/b&gt; that builds apps&lt;/p&gt;</description><pubDate>Mon, 05 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>AI company faces lawsuit over stock valuation</title><link>https://example.com/lawsuit</link>
<description>Earnings news</description></item>
<item><title>Evil link</title><link>javascript:alert(1)</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Open-source model released with a new reasoning benchmark</title>
<link rel="alternate" href="https://example.org/model"/><updated>2026-10-04T08:00:00Z</updated>
<summary>Try the new model today</summary></entry>
<entry><title>Startup launches new AI coding agent for beginners</title><link href="https://dup.example/x"/></entry>
</feed>"""


def test_news_parsing_filtering_and_dedupe(monkeypatch):
    from src import news
    monkeypatch.setenv("CUTIA_NEWS_FEEDS", "A|https://a.example/rss,B|https://b.example/atom")
    fixtures = {"A": RSS, "B": ATOM}
    items, errors = news.collect(lambda su: (news.parse_feed(fixtures[su[0]], su[0]), None))
    titles = [it["title"] for it in items]
    assert "Startup launches new AI coding agent for beginners" in titles
    assert "Open-source model released with a new reasoning benchmark" in titles
    assert not any("lawsuit" in t for t in titles)              # filtrat
    assert len(titles) == 2                                       # duplicat scos, link javascript: ignorat
    agent = next(it for it in items if "agent" in it["title"])
    assert agent["summary"] == "A free app that builds apps"      # fără HTML
    assert agent["category"] == "launch"


def test_news_endpoint_without_ai(monkeypatch):
    from src import news
    monkeypatch.setattr(news, "_cache", {"at": 0.0, "items": [], "errors": [], "curated": {}})
    monkeypatch.setattr(news, "_fetch", lambda su: (news.parse_feed(RSS, "Test"), None))
    monkeypatch.setattr(news, "feeds", lambda: [("Test", "https://t.example/rss")])
    ana = login("Ana")
    data = client.get("/api/news", headers=ana).json()
    assert data["curated"] is False
    assert data["items"][0]["link"] == "https://example.com/agent"
    assert client.get("/api/news").status_code == 401


# ---------------------------------------------------------------- traduceri

def test_all_languages_are_complete():
    import shutil
    import subprocess
    from pathlib import Path
    if not shutil.which("node"):
        pytest.skip("node nu e instalat")
    script = Path(__file__).parent / "check_i18n.js"
    r = subprocess.run(["node", str(script), "en", "ro", "fr", "it", "es", "de"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert set(app_module.ai.LANGS) == {"ro", "en", "fr", "it", "es", "de"}
    assert all(len(v) == len(app_module.ai.LANGS) for v in app_module.MESSAGES.values())


def test_change_password():
    ana = login("Ana")
    body = {"current": "gresita!!", "new": "parola-noua-1"}
    assert client.post("/api/me/password", json=body, headers=ana).status_code == 403
    assert client.post("/api/me/password", json={**body, "current": "parola-test", "new": "scurt"}, headers=ana).status_code == 400
    assert client.post("/api/me/password", json={**body, "current": "parola-test"}, headers=ana).status_code == 200
    assert client.post("/api/login", json={"email": "ana@test.ro", "password": "parola-noua-1"}).status_code == 200
    me = client.get("/api/me", headers=ana).json()
    assert me["email"] == "ana@test.ro" and me["has_password"] is True


# ---------------------------------------------------------------- retragere & ciorne

def make_proposal(headers, title="Quiz"):
    body = {"title": title, "description": "Un quiz.", "audience": "Clasa", "approved": True}
    return client.post("/api/proposals", json=body, headers=headers).json()["id"]


def test_author_can_withdraw_and_restore_a_proposal():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer")
    pid = make_proposal(ana)
    make_proposal(ana, "A doua idee")                      # se pot trimite mai multe
    client.post(f"/api/proposals/{pid}/vote", headers=bob)
    assert client.post(f"/api/proposals/{pid}/withdraw", json={"reason": "resolved"}, headers=bob).status_code == 403

    r = client.post(f"/api/proposals/{pid}/withdraw", json={"reason": "resolved", "note": "Am găsit o soluție"}, headers=ana)
    assert r.json()["status"] == "withdrawn" and r.json()["withdrawn_reason"] == "resolved"
    assert [p["title"] for p in client.get("/api/proposals", headers=bob).json()] == ["A doua idee"]
    assert len(client.get("/api/proposals", headers=ana).json()) == 2        # autorul o vede în continuare
    assert len(client.get("/api/proposals", headers=trainer).json()) == 2
    assert client.post(f"/api/proposals/{pid}/vote", headers=bob).status_code == 400
    assert client.post(f"/api/proposals/{pid}/choose", headers=trainer).status_code == 400
    # Idee retrasă = fără puncte pentru idee și voturi; rămâne doar a doua idee (+5)
    assert client.get("/api/points/me", headers=ana).json()["total"] == 5

    assert client.post(f"/api/proposals/{pid}/restore", headers=ana).json()["status"] == "active"
    assert len(client.get("/api/proposals", headers=bob).json()) == 2


def test_drafts_are_private_and_limited():
    ana, bob = login("Ana"), login("Bob")
    d = client.post("/api/drafts", json={"title": "Idee", "description": "ceva"}, headers=ana).json()
    assert client.get("/api/drafts", headers=bob).json() == []
    assert client.put(f"/api/drafts/{d['id']}", json={"title": "x"}, headers=bob).status_code == 404
    assert client.delete(f"/api/drafts/{d['id']}", headers=bob).status_code == 404
    r = client.put(f"/api/drafts/{d['id']}", json={"title": "Idee mai bună", "description": "ceva", "audience": "noi"}, headers=ana)
    assert r.json()["title"] == "Idee mai bună" and "owner" not in r.json()
    for _ in range(19):
        client.post("/api/drafts", json={"title": "x"}, headers=ana)
    assert client.post("/api/drafts", json={"title": "prea multe"}, headers=ana).status_code == 400
    assert client.delete(f"/api/drafts/{d['id']}", headers=ana).status_code == 200
    assert len(client.get("/api/drafts", headers=ana).json()) == 19


# ---------------------------------------------------------------- Supabase Auth (cu un Supabase fals)

import json as _json
import httpx
from src import supa


class FakeSupabase:
    """Imită API-ul REST Supabase Auth: conturi, confirmare pe email, resetare."""

    def __init__(self, autoconfirm=False, google=True):
        self.users, self.tokens, self.sent = {}, {}, []
        self.autoconfirm, self.google = autoconfirm, google

    def token_for(self, email, provider="email"):
        tok = f"tok-{len(self.tokens)}-{email}"
        self.tokens[tok] = (email, provider)
        return tok

    def confirm(self, email):
        self.users[email]["confirmed"] = True
        return self.token_for(email)

    def handler(self, request):
        assert request.headers["apikey"] == "anon-test"
        path, body = request.url.path, _json.loads(request.content or b"{}")
        if path == "/auth/v1/settings":
            return httpx.Response(200, json={"external": {"google": self.google}, "mailer_autoconfirm": self.autoconfirm})
        if path == "/auth/v1/signup":
            if body["email"] in self.users:
                return httpx.Response(422, json={"code": "user_already_exists", "msg": "User already registered"})
            self.users[body["email"]] = {"password": body["password"], "confirmed": self.autoconfirm, "name": body["data"]["name"]}
            if self.autoconfirm:
                return httpx.Response(200, json={"access_token": self.token_for(body["email"])})
            self.sent.append(("confirm", body["email"]))
            return httpx.Response(200, json={"id": "u1", "email": body["email"]})
        if path == "/auth/v1/token":
            u = self.users.get(body["email"])
            if not u or u["password"] != body["password"]:
                return httpx.Response(400, json={"code": "invalid_credentials", "msg": "Invalid login credentials"})
            if not u["confirmed"]:
                return httpx.Response(400, json={"code": "email_not_confirmed", "msg": "Email not confirmed"})
            return httpx.Response(200, json={"access_token": self.token_for(body["email"])})
        if path == "/auth/v1/recover":
            self.sent.append(("recover", body["email"]))
            return httpx.Response(200, json={})
        if path == "/auth/v1/user":
            found = self.tokens.get(request.headers["authorization"].removeprefix("Bearer "))
            if not found:
                return httpx.Response(401, json={"msg": "invalid JWT"})
            email, provider = found
            if request.method == "PUT":
                self.users.setdefault(email, {"confirmed": True, "name": email})["password"] = body["password"]
                return httpx.Response(200, json={"email": email})
            u = self.users.get(email, {"confirmed": True, "name": "Google " + email})
            return httpx.Response(200, json={
                "email": email, "email_confirmed_at": "2026-01-01T00:00:00Z" if u["confirmed"] else None,
                "app_metadata": {"provider": provider}, "user_metadata": {"name": u["name"]}})
        return httpx.Response(404)


@pytest.fixture
def fake_supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setenv("SUPABASE_URL", "https://proiect.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test")
    monkeypatch.setattr(supa, "_transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(supa, "_settings_cache", {"at": 0.0, "value": None})
    app_module._recover_sent.clear()
    app_module.db["supabase_pending"] = {}
    return fake


def test_supabase_signup_needs_email_confirmation(fake_supabase):
    cfg = client.get("/api/config").json()
    assert cfg["supabase"] == {"url": "https://proiect.supabase.co", "google": True}
    assert "anon-test" not in _json.dumps(cfg)  # cheia rămâne pe server
    r = client.post("/api/register", json={"name": "Madalina", "email": "madalina@test.ro", "password": "parola-buna"})
    assert r.status_code == 201 and r.json()["confirm_email"] is True and "token" not in r.json()
    assert fake_supabase.sent == [("confirm", "madalina@test.ro")]
    # Fără confirmare nu se poate intra
    r = client.post("/api/login", json={"email": "madalina@test.ro", "password": "parola-buna"})
    assert r.status_code == 403
    # Linkul din email aduce tokenul înapoi; serverul îl verifică la Supabase
    r = client.post("/api/auth/supabase", json={"access_token": fake_supabase.confirm("madalina@test.ro")})
    assert r.status_code == 200 and r.json()["name"] == "Madalina" and r.json()["role"] == "student"
    r = client.post("/api/login", json={"email": "madalina@test.ro", "password": "parola-buna"})
    assert r.status_code == 200
    me = client.get("/api/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()
    assert me["has_password"] is True
    # Parola nu e salvată la noi
    assert "hash" not in app_module.db["users"]["madalina@test.ro"]


def test_supabase_rejects_fake_tokens_and_wrong_passwords(fake_supabase):
    assert client.post("/api/auth/supabase", json={"access_token": "token-inventat"}).status_code == 401
    fake_supabase.autoconfirm = True
    assert client.post("/api/register", json={"name": "Ana", "email": "ana@test.ro", "password": "parola-buna"}).status_code == 201
    assert client.post("/api/login", json={"email": "ana@test.ro", "password": "gresit!!"}).status_code == 401
    assert client.post("/api/login", json={"email": "nimeni@test.ro", "password": "gresit!!"}).json()["detail"] == \
        client.post("/api/login", json={"email": "ana@test.ro", "password": "gresit!!"}).json()["detail"]
    for _ in range(3):
        client.post("/api/login", json={"email": "ana@test.ro", "password": "gresit!!"})
    assert client.post("/api/login", json={"email": "ana@test.ro", "password": "parola-buna"}).status_code == 429


def test_supabase_trainer_email_needs_verified_email(fake_supabase, monkeypatch):
    # Fără confirmare pe email, oricine ar putea pretinde emailul trainerului
    fake_supabase.autoconfirm = True
    r = client.post("/api/register", json={"name": "Impostor", "email": "radu@test.ro", "password": "parola-buna"})
    assert r.json()["role"] == "student"
    # Cu confirmare pe email (sau Google), emailul din TRAINER_EMAILS devine trainer
    app_module.db["users"].clear()
    monkeypatch.setattr(supa, "_settings_cache", {"at": 0.0, "value": None})
    fake_supabase.autoconfirm = False
    r = client.post("/api/auth/supabase", json={"access_token": fake_supabase.token_for("radu@test.ro", "google")})
    assert r.json()["role"] == "trainer"


def test_supabase_class_code_and_google(fake_supabase, monkeypatch):
    monkeypatch.setattr(app_module, "CLASS_CODE", "VIBE2026")
    google_token = fake_supabase.token_for("vlad@gmail.com", "google")
    assert client.post("/api/auth/supabase", json={"access_token": google_token}).status_code == 403
    r = client.post("/api/auth/supabase", json={"access_token": google_token, "class_code": "VIBE2026"})
    assert r.status_code == 200 and r.json()["name"] == "Google vlad@gmail.com"
    # Codul verificat la „Cont nou” rămâne valabil când revine din linkul de confirmare
    assert client.post("/api/register", json={"name": "Ana", "email": "ana@test.ro", "password": "parola-buna"}).status_code == 403
    assert client.post("/api/register", json={"name": "Ana", "email": "ana@test.ro", "password": "parola-buna", "class_code": "VIBE2026"}).json()["confirm_email"]
    assert client.post("/api/auth/supabase", json={"access_token": fake_supabase.confirm("ana@test.ro")}).status_code == 200


def test_supabase_password_reset(fake_supabase):
    fake_supabase.autoconfirm = True
    client.post("/api/register", json={"name": "Ana", "email": "ana@test.ro", "password": "parola-buna"})
    for _ in range(3):
        assert client.post("/api/auth/supabase/recover", json={"email": "ana@test.ro"}).status_code == 200
    assert client.post("/api/auth/supabase/recover", json={"email": "ana@test.ro"}).status_code == 429
    # Același răspuns pentru un email fără cont
    assert client.post("/api/auth/supabase/recover", json={"email": "nimeni@test.ro"}).json() == {"ok": True}
    link_token = fake_supabase.token_for("ana@test.ro")
    assert client.post("/api/auth/supabase/new-password", json={"access_token": link_token, "password": "scurta"}).status_code == 400
    r = client.post("/api/auth/supabase/new-password", json={"access_token": link_token, "password": "parola-noua-1"})
    assert r.status_code == 200 and r.json()["name"] == "Ana"
    assert client.post("/api/login", json={"email": "ana@test.ro", "password": "parola-noua-1"}).status_code == 200
    # Schimbarea parolei din Setări cere parola actuală
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.post("/api/me/password", headers=h, json={"current": "gresit!!", "new": "parola-noua-2"}).status_code == 403
    assert client.post("/api/me/password", headers=h, json={"current": "parola-noua-1", "new": "parola-noua-2"}).status_code == 200
    assert fake_supabase.users["ana@test.ro"]["password"] == "parola-noua-2"


def test_supabase_trainer_reset_sends_email_and_privacy_holds(fake_supabase):
    fake_supabase.autoconfirm = True
    a = client.post("/api/register", json={"name": "Ana", "email": "ana@test.ro", "password": "parola-buna"}).json()
    b = client.post("/api/register", json={"name": "Vlad", "email": "vlad@test.ro", "password": "parola-buna"}).json()
    ha, hb = ({"Authorization": f"Bearer {x['token']}"} for x in (a, b))
    client.post("/api/questions", headers=ha, json={"text": "Cum pun cheia API în .env?", "category": "security"})
    assert client.get("/api/questions", headers=hb).json() == []
    trainer = client.post("/api/register", json={"name": "Radu", "email": "radu2@test.ro", "password": "parola-buna", "trainer_code": "secret"}).json()
    assert trainer["role"] == "trainer"
    r = client.post("/api/students/ana@test.ro/reset-password", headers={"Authorization": f"Bearer {trainer['token']}"})
    assert r.json() == {"temporary_password": None, "email_sent": True}
    assert ("recover", "ana@test.ro") in fake_supabase.sent
    assert client.post("/api/students/ana@test.ro/reset-password", headers=hb).status_code == 403


def test_supabase_down_gives_clear_error(fake_supabase, monkeypatch):
    def broken(request):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(supa, "_transport", httpx.MockTransport(broken))
    r = client.post("/api/login", json={"email": "ana@test.ro", "password": "parola-buna"})
    assert r.status_code == 503 and "Supabase" in r.json()["detail"]


def test_supabase_trainer_email_does_not_skip_class_code(fake_supabase, monkeypatch):
    monkeypatch.setattr(app_module, "CLASS_CODE", "VIBE2026")
    fake_supabase.autoconfirm = True
    r = client.post("/api/register", json={"name": "Impostor", "email": "radu@test.ro", "password": "parola-buna"})
    assert r.status_code == 403
