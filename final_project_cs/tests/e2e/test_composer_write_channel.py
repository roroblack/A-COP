from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
import yaml
from fastapi.testclient import TestClient

import app.presentation.composer_auth as composer_auth
from app.presentation.api.app import create_app


@pytest.fixture()
def configured(monkeypatch):
    settings = SimpleNamespace(composer_jwt_secret="test-jwt-secret", composer_issuer_secret="test-issuer-secret")
    monkeypatch.setattr(composer_auth, "get_settings", lambda: settings)


def _token(scope: str | list[str], *, expired: bool = False, secret: str = "test-jwt-secret") -> str:
    scopes = [scope] if isinstance(scope, str) else scope
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": "test-actor", "aud": "final_project_cs", "scope": scopes,
                       "iat": now - timedelta(hours=2) if expired else now,
                       "exp": now - timedelta(minutes=1) if expired else now + timedelta(minutes=30),
                       "jti": str(uuid4())}, secret, algorithm="HS256")


def _client(tmp_path: Path, monkeypatch) -> tuple[TestClient, Path]:
    source = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    app = create_app(classifier=lambda _: {"intent": "billing", "issue_code": "x", "sentiment": "neutral"})
    app.state.project_config_path = path
    app.state.composer_audit_path = tmp_path / "composer_events.jsonl"
    return TestClient(app), path


def _auth(scope: str | list[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(scope)}"}


def test_expired_token_is_rejected(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get("/composer/current", headers={"Authorization": f"Bearer {_token('composer:read', expired=True)}"})
    assert response.status_code == 401


def test_forged_signature_is_rejected(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get("/composer/current", headers={"Authorization": f"Bearer {_token('composer:read', secret='wrong')}"})
    assert response.status_code == 401


def test_token_issue_and_current_endpoint(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    issued = client.post("/auth/token", headers={"Authorization": "Bearer test-issuer-secret"},
                         json={"sub": "final_project_ui", "scope": ["composer:read"]})
    assert issued.status_code == 200
    current = client.get("/composer/current", headers={"Authorization": f"Bearer {issued.json()['access_token']}"})
    assert current.status_code == 200
    assert "revision" in current.json()


def test_concurrent_apply_one_wins_one_gets_409(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    payloads = []
    for index, team in enumerate(current["config"]["teams"]):
        candidate = dict(current["config"])
        candidate["teams"] = [dict(item) for item in current["config"]["teams"]]
        candidate["teams"][index]["active"] = not team["active"]
        payloads.append(candidate)
    results = [None, None]

    def apply(index: int):
        results[index] = client.post("/composer/apply", headers=_auth("composer:write"), json={
            "config": payloads[index], "base_revision": current["revision"], "reason": "concurrent test"})

    threads = [threading.Thread(target=apply, args=(index,)) for index in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert sorted(response.status_code for response in results) == [200, 409]
