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
    app_module.db.update({"users": {}, "questions": [], "proposals": [], "submissions": [], "next_id": 1})
    app_module.sessions.clear()


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
