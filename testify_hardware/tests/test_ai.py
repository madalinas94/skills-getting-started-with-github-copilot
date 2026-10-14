"""Asistentul AI, testat cu un client Claude simulat (fără cheie reală și fără internet)."""

import json
import os
import tempfile
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from app import assistant_ai


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TESTIFY_FISCAL_FEED", "")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("TESTIFY_DB", os.path.join(tmp, "test.db"))
        from app.main import app
        with TestClient(app) as test_client:
            test_client.post("/api/auth/setup", json={"password": "parola123", "demo": True})
            yield test_client


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def fake_reply(text="În septembrie ai încasat **152.655 lei**.", stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, model=assistant_ai.AI_MODEL,
                           content=[SimpleNamespace(type="thinking", thinking=""),
                                    SimpleNamespace(type="text", text=text)])


def use_fake(monkeypatch, messages: FakeMessages):
    monkeypatch.setattr(assistant_ai, "make_client",
                        lambda conn: SimpleNamespace(beta=SimpleNamespace(messages=messages)))


def enable(client, key="sk-ant-test-1234567890abcd"):
    return client.put("/api/ai/settings", json={"enabled": True, "api_key": key}).json()


def test_disabled_by_default_and_needs_a_key(client):
    status = client.get("/api/ai/status").json()
    assert status["enabled"] is False and status["has_key"] is False
    assert client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "Salut"}]}).status_code == 400
    # Pornit, dar fără cheie: tot dezactivat.
    assert client.put("/api/ai/settings", json={"enabled": True}).json()["enabled"] is False


def test_key_is_never_sent_back_in_full(client):
    status = enable(client)
    assert status["enabled"] is True
    assert status["key_hint"] == "sk-ant-…abcd"
    assert "sk-ant-test" not in json.dumps(client.get("/api/settings").json())
    cleared = client.put("/api/ai/settings", json={"enabled": True, "clear_key": True}).json()
    assert cleared["has_key"] is False and cleared["enabled"] is False


def test_chat_sends_business_data_and_returns_the_answer(client, monkeypatch):
    enable(client)
    fake = FakeMessages(fake_reply())
    use_fake(monkeypatch, fake)
    history = [
        {"role": "assistant", "content": "Bună, sunt Testi!"},      # salutul local nu se trimite primul
        {"role": "user", "content": "Cât am încasat în septembrie?"},
    ]
    response = client.post("/api/ai/chat", json={"messages": history})
    assert response.status_code == 200
    assert response.json()["reply"] == "În septembrie ai încasat **152.655 lei**."

    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["messages"] == [{"role": "user", "content": "Cât am încasat în septembrie?"}]
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    data = json.loads(call["system"][1]["text"].split("\n", 1)[1])
    september = next(m for m in data["months"] if m["month"] == "2026-09")
    assert september["revenue"] == 152654.62 and september["profit"] == 16025.67
    assert data["receivables"]["total"] > 0 and len(data["products"]) == 14
    assert "parola" not in call["system"][1]["text"] and "sk-ant" not in call["system"][1]["text"]


def test_refusal_gets_a_polite_answer(client, monkeypatch):
    enable(client)
    use_fake(monkeypatch, FakeMessages(fake_reply(text="", stop_reason="refusal")))
    reply = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "x"}]}).json()["reply"]
    assert reply.startswith("Nu pot răspunde")


def test_api_errors_are_explained(client, monkeypatch):
    enable(client)
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    bad_key = anthropic.AuthenticationError("invalid", response=httpx2.Response(401, request=request), body=None)
    use_fake(monkeypatch, FakeMessages(error=bad_key))
    response = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "Salut"}]})
    assert response.status_code == 400 and "Cheia API" in response.json()["detail"]

    use_fake(monkeypatch, FakeMessages(error=anthropic.APIConnectionError(request=request)))
    response = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "Salut"}]})
    assert response.status_code == 503 and "internet" in response.json()["detail"]
