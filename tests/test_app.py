import os
import tempfile

os.environ["CUTIA_PERSIST"] = "0"
os.environ["CUTIA_AI"] = "off"
os.environ["TRAINER_CODE"] = "secret"
os.environ["CUTIA_UPLOADS"] = tempfile.mkdtemp()

import pytest
from fastapi.testclient import TestClient

from src import app as app_module

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def reset_db():
    app_module.db.update({
        "users": {}, "sessions": {}, "prefs": {}, "questions": [], "proposals": [], "submissions": [],
        "messages": [], "assignments": [], "announcements": [], "bonuses": [], "next_id": 1,
    })


def login(name, role="student", code=None, password="parola-test"):
    r = client.post("/api/login", json={"name": name, "role": role, "code": code, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_trainer_needs_code():
    r = client.post("/api/login", json={"name": "T", "role": "trainer", "code": "wrong"})
    assert r.status_code == 403
    login("T", "trainer", "secret")


def test_questions_visible_only_to_author_and_trainer():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer", "secret")

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
    trainer = login("Radu", "trainer", "secret")
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
    trainer = login("Radu", "trainer", "secret")
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
    ana = login("Ana", password="parola-ana")
    client.post("/api/questions", json={"text": "Întrebarea Anei"}, headers=ana)

    # Studentul B încearcă să intre cu numele Anei
    r = client.post("/api/login", json={"name": "ana", "role": "student", "password": "ghicit"})
    assert r.status_code == 401

    bob = login("Bob", password="parola-bob")
    assert client.get("/api/questions", headers=bob).json() == []
    assert len(client.get("/api/questions", headers=login("Ana", password="parola-ana")).json()) == 1


def test_password_required_and_not_exposed():
    r = client.post("/api/login", json={"name": "Ana", "role": "student", "password": "123"})
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
    r = client.post("/api/login", json={"name": "T", "role": "trainer", "code": "x"}, headers={"X-Lang": "en"})
    assert r.json()["detail"] == "Wrong trainer code."
    r = client.post("/api/login", json={"name": "T", "role": "trainer", "code": "x"})
    assert r.json()["detail"] == "Cod de trainer greșit."


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
    trainer = login("Radu", "trainer", "secret")
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
    trainer = login("Radu", "trainer", "secret")
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
    r = client.post("/api/login", json={"name": "T", "role": "trainer", "code": "x"}, headers={"X-Lang": "fr"})
    assert r.json()["detail"] == "Code formateur incorrect."


# ---------------------------------------------------------------- mesaje directe

def test_direct_messages_are_private():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer", "secret")
    client.post("/api/dm", json={"text": "Bună! Am o întrebare despre temă."}, headers=ana)
    assert client.get("/api/dm", headers=bob).json()["messages"] == []
    assert client.get("/api/dm/ana", headers=bob).status_code == 403
    assert client.get("/api/dm/unread", headers=trainer).json()["unread"] == 1

    threads = client.get("/api/dm", headers=trainer).json()["threads"]
    ana_thread = next(t for t in threads if t["student_key"] == "ana")
    assert ana_thread["unread"] == 1
    assert len(client.get("/api/dm/ana", headers=trainer).json()["messages"]) == 1
    assert client.get("/api/dm/unread", headers=trainer).json()["unread"] == 0  # citit

    client.post("/api/dm/ana", json={"text": "Sigur, spune!"}, headers=trainer)
    assert client.get("/api/dm/unread", headers=ana).json()["unread"] == 1
    msgs = client.get("/api/dm", headers=ana).json()["messages"]
    assert [m["from_role"] for m in msgs] == ["student", "trainer"]
    assert client.get("/api/dm/unread", headers=ana).json()["unread"] == 0
    assert client.post("/api/dm/nimeni", json={"text": "x"}, headers=trainer).status_code == 404


# ---------------------------------------------------------------- puncte

def test_points_follow_the_rules():
    ana, bob, cris = login("Ana"), login("Bob"), login("Cris")
    trainer = login("Radu", "trainer", "secret")
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
    client.post("/api/points/bonus", json={"student_key": "ana", "points": 7, "reason": "Ajutor colegilor"},
                headers=trainer)

    me = client.get("/api/points/me", headers=ana).json()
    # 10 predare + 5 la timp + 25 revizuit + 5 idee + 4 voturi + 30 aleasă + 6 întrebări (max 3/zi) + 7 bonus
    assert me["total"] == 92
    assert me["level"]["key"] == "apprentice"
    assert {"first_homework", "first_idea", "chosen", "first_question"} <= set(me["badges"])


def test_bonus_rules_and_access():
    ana = login("Ana")
    trainer = login("Radu", "trainer", "secret")
    body = {"student_key": "ana", "points": 10, "reason": "x"}
    assert client.post("/api/points/bonus", json=body, headers=ana).status_code == 403
    assert client.post("/api/points/bonus", json={**body, "points": 0}, headers=trainer).status_code == 400
    assert client.post("/api/points/bonus", json={**body, "reason": " "}, headers=trainer).status_code == 400
    assert client.post("/api/points/bonus", json={**body, "student_key": "zz"}, headers=trainer).status_code == 404
    assert client.get("/api/points/ana", headers=ana).status_code == 403


def test_leaderboard_respects_hide():
    ana, bob = login("Ana"), login("Bob")
    trainer = login("Radu", "trainer", "secret")
    client.patch("/api/me", json={"hide_from_leaderboard": True}, headers=ana)
    names_bob = [r["name"] for r in client.get("/api/leaderboard", headers=bob).json()]
    assert "Ana" not in names_bob and "Bob" in names_bob
    assert any(r["me"] for r in client.get("/api/leaderboard", headers=ana).json())  # se vede pe sine
    assert "Ana" in [r["name"] for r in client.get("/api/leaderboard", headers=trainer).json()]
    assert "key" not in client.get("/api/leaderboard", headers=bob).json()[0]


# ---------------------------------------------------------------- teme & anunțuri

def test_assignments_and_announcements():
    ana = login("Ana")
    trainer = login("Radu", "trainer", "secret")
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
