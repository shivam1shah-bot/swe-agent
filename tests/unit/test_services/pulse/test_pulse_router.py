"""
Tests for the Pulse API router endpoints.

Uses FastAPI TestClient with dependency overrides to test HTTP layer,
Pydantic validation, and error handling.
"""

import pytest
from unittest.mock import patch
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from src.api.routers.pulse import router
from src.api.dependencies import get_db_session, get_current_user
import src.api.routers.pulse as pulse_mod


def _mock_auth_ok():
    return {"username": "test-user", "role": "admin"}


def _mock_auth_fail():
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(router, prefix="/pulse")
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_current_user] = _mock_auth_ok
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client(db):
    app = FastAPI()
    app.include_router(router, prefix="/pulse")
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_current_user] = _mock_auth_fail
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestHealthEndpoint:

    def test_health_returns_ok(self, db):
        app = FastAPI()
        app.include_router(router, prefix="/pulse")
        c = TestClient(app)
        resp = c.get("/pulse/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy", "service": "pulse"}


class TestReadEndpointsAuth:

    def test_overview_requires_auth(self, unauth_client):
        resp = unauth_client.get("/pulse/overview")
        assert resp.status_code == 401

    def test_repos_requires_auth(self, unauth_client):
        resp = unauth_client.get("/pulse/repos")
        assert resp.status_code == 401

    def test_commits_requires_auth(self, unauth_client):
        resp = unauth_client.get("/pulse/commits")
        assert resp.status_code == 401

    def test_prompts_requires_auth(self, unauth_client):
        resp = unauth_client.get("/pulse/prompts")
        assert resp.status_code == 401

    def test_people_requires_auth(self, unauth_client):
        resp = unauth_client.get("/pulse/people")
        assert resp.status_code == 401


class TestReadEndpoints:

    def test_overview_empty_db(self, client):
        resp = client.get("/pulse/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost_usd" in data
        assert data["total_prompts"] == 0

    def test_repos_empty_db(self, client):
        resp = client.get("/pulse/repos")
        assert resp.status_code == 200
        assert resp.json()["repos"] == []

    def test_commits_empty_db(self, client):
        resp = client.get("/pulse/commits")
        assert resp.status_code == 200
        assert resp.json()["commits"] == []

    def test_prompts_empty_db(self, client):
        resp = client.get("/pulse/prompts")
        assert resp.status_code == 200
        assert resp.json()["prompts"] == []

    def test_people_empty_db(self, client):
        resp = client.get("/pulse/people")
        assert resp.status_code == 200
        assert resp.json()["people"] == []

    def test_service_error_returns_500(self, client):
        with patch.object(pulse_mod, "aggregate_overview", side_effect=RuntimeError("boom")):
            resp = client.get("/pulse/overview")
            assert resp.status_code == 500
            assert resp.json()["detail"] == "Internal server error"


class TestIngestEndpoints:

    def test_ingest_turn_valid(self, client):
        payload = {"repo": "my-repo", "tokens": {"input_tokens": 100, "output_tokens": 50,
                   "cache_read_tokens": 0, "cache_creation_tokens": 0}}
        resp = client.post("/pulse/ingest/turn", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_ingest_turn_invalid_turn_type(self, client):
        resp = client.post("/pulse/ingest/turn", json={"repo": "r", "turn_type": "bad"})
        assert resp.status_code == 422

    def test_ingest_turn_empty_repo(self, client):
        resp = client.post("/pulse/ingest/turn", json={"repo": "   "})
        assert resp.status_code == 422

    def test_ingest_edit_valid(self, client):
        resp = client.post("/pulse/ingest/edit", json={"repo": "my-repo"})
        assert resp.status_code == 200

    def test_ingest_commit_valid(self, client):
        resp = client.post("/pulse/ingest/commit", json={"commit_hash": "abc123", "repo": "r"})
        assert resp.status_code == 200

    def test_ingest_commit_empty_hash(self, client):
        resp = client.post("/pulse/ingest/commit", json={"commit_hash": "   "})
        assert resp.status_code == 422

    def test_ingest_no_auth_needed(self, unauth_client):
        resp = unauth_client.post("/pulse/ingest/turn", json={"repo": "r"})
        assert resp.status_code == 200
