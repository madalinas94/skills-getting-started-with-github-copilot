import os

os.environ["CUTIA_PERSIST"] = "0"
os.environ["CUTIA_AI"] = "off"
os.environ["TRAINER_CODE"] = "secret"

import pytest
from fastapi.testclient import TestClient

from src import app as app_module

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def reset_db():
    app_module.db.update({"users": {}, "questions": [], "proposals": [], "next_id": 1})
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
