# Copyright 2025 msq
from __future__ import annotations

from fastapi.testclient import TestClient

from emergency_agents.api.main import app


def test_healthz():
    client = TestClient(app)
    r = client.get('/healthz')
    assert r.status_code == 200
    assert r.json().get('status') == 'ok'


def test_threads_lifecycle():
    client = TestClient(app)
    rid = 'unit_test_001'
    r = client.post(f'/threads/start?rescue_id={rid}&user_id=u1')
    assert r.status_code == 200
    r = client.post(f'/threads/resume?rescue_id={rid}')
    assert r.status_code == 200

