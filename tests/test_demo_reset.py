import pytest
from fastapi.testclient import TestClient
from evalforge.server.app import app
from evalforge.config import get_settings, Settings, set_settings
from evalforge.storage.repository import Repository

client = TestClient(app)

def test_demo_reset_disabled_outside_demo_mode(monkeypatch):
    """Proves POST /api/demo/reset returns 403 when DEMO_MODE is false."""
    s = Settings(demo_mode=False, demo_admin_key="secret-key")
    set_settings(s)

    resp = client.post("/api/demo/reset", headers={"X-Demo-Key": "secret-key"})
    assert resp.status_code == 403
    assert "disabled outside demo mode" in resp.json()["detail"].lower()

def test_demo_reset_requires_authentication():
    """Proves POST /api/demo/reset returns 401 when authorization is missing or invalid."""
    s = Settings(demo_mode=True, demo_admin_key="valid-secret-key")
    set_settings(s)

    # Missing header
    resp_no_auth = client.post("/api/demo/reset")
    assert resp_no_auth.status_code == 401

    # Invalid header
    resp_bad_auth = client.post("/api/demo/reset", headers={"X-Demo-Key": "wrong-secret"})
    assert resp_bad_auth.status_code == 401

def test_demo_reset_authenticated_and_idempotent(temp_db_path):
    """Proves POST /api/demo/reset clears state, reseeds sample runs, and is idempotent."""
    s = Settings(demo_mode=True, demo_admin_key="test-key-2026", db_path=temp_db_path)
    set_settings(s)

    # First reset call
    resp1 = client.post("/api/demo/reset", headers={"X-Demo-Key": "test-key-2026"})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "reset_successful"
    assert len(data1["runs_seeded"]) == 2

    # Second reset call (idempotent)
    resp2 = client.post("/api/demo/reset", headers={"X-Demo-Key": "test-key-2026"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "reset_successful"
    assert len(data2["runs_seeded"]) == 2

    # Verify repository has exactly 2 runs after reseeding
    repo = Repository(temp_db_path)
    runs = repo.list_runs()
    assert len(runs) == 2
