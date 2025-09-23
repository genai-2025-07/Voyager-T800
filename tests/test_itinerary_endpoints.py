from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from fastapi.testclient import TestClient

from app.main import app


class FakeDynamoDBClient:
    def __init__(self):
        self._store: dict[tuple[str, str], dict[str, Any]] = {}
        self.table_name = 'fake_session_metadata'

    def put_item(self, session_metadata) -> int:  # matches interface
        key = (session_metadata.user_id, session_metadata.session_id)
        self._store[key] = {
            'user_id': session_metadata.user_id,
            'session_id': session_metadata.session_id,
            'session_summary': session_metadata.session_summary,
            'started_at': session_metadata.started_at,
            'messages': list(session_metadata.messages),
        }
        return 200

    def get_item(self, user_id: str, session_id: str) -> dict | None:
        return self._store.get((user_id, session_id))

    def delete_item(self, user_id: str, session_id: str) -> int:
        self._store.pop((user_id, session_id), None)
        return 200

    def list_sessions(self, user_id: str) -> list[dict]:
        items = [v for (u, _), v in self._store.items() if u == user_id]
        return items


@asynccontextmanager
async def _no_lifespan(_app):
    # Skip real startup/shutdown
    yield


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    # Prevent real external initializations
    monkeypatch.setattr(app.router, 'lifespan_context', _no_lifespan, raising=True)
    # Inject fakes
    app.state.dynamodb_client = FakeDynamoDBClient()
    app.state.weaviate_db_manager = None
    # Test client
    with TestClient(app) as c:
        yield c


def test_create_session(client: TestClient):
    resp = client.post('/api/v1/itinerary/sessions', json={'user_id': 'anonymous'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    assert data['user_id'] == 'anonymous'
    assert isinstance(data['session_id'], str) and data['session_id'].startswith('voyager_session_')


def test_list_and_get_session_flow(client: TestClient):
    # Initially empty
    r0 = client.get('/api/v1/itinerary/sessions', params={'user_id': 'u1'})
    assert r0.status_code == 200
    assert r0.json()['sessions'] == []

    # Create
    rc = client.post('/api/v1/itinerary/sessions', json={'user_id': 'u1'})
    sid = rc.json()['session_id']

    # List again
    r1 = client.get('/api/v1/itinerary/sessions', params={'user_id': 'u1'})
    assert r1.status_code == 200
    sessions = r1.json()['sessions']
    assert any(item.get('session_id') == sid for item in sessions)

    # Get session data
    rg = client.get(f'/api/v1/itinerary/{sid}', params={'user_id': 'u1'})
    assert rg.status_code == 200
    sdata = rg.json()
    assert sdata['session_id'] == sid
    assert sdata['user_id'] == 'u1'
    assert isinstance(sdata['messages'], list)


def test_delete_session(client: TestClient):
    # Create
    rc = client.post('/api/v1/itinerary/sessions', json={'user_id': 'u2'})
    sid = rc.json()['session_id']

    # Delete
    rd = client.delete(f'/api/v1/itinerary/sessions/{sid}', params={'user_id': 'u2'})
    assert rd.status_code == 200
    assert rd.json()['deleted'] is True

    # Verify not found
    rg = client.get(f'/api/v1/itinerary/{sid}', params={'user_id': 'u2'})
    assert rg.status_code == 404


def test_generate_itinerary_stores_messages(monkeypatch, client: TestClient):
    # Mock chain full_response to return a static itinerary
    from app.chains import itinerary_chain

    def fake_full_response(query: str, session_id: str) -> str:
        return f'Itinerary for: {query} @ {session_id}'

    monkeypatch.setattr(itinerary_chain, 'full_response', fake_full_response, raising=True)

    # Create a session
    rc = client.post('/api/v1/itinerary/sessions', json={'user_id': 'u3'})
    sid = rc.json()['session_id']

    # Generate
    q = 'Plan a 3-day trip to Rome'
    rg = client.post('/api/v1/itinerary/generate', json={'query': q, 'session_id': sid, 'user_id': 'u3'})
    assert rg.status_code == 200
    payload = rg.json()
    assert payload['success'] is True
    assert payload['session_id'] == sid
    assert 'Rome' in payload['itinerary']

    # Validate two messages appended (user + assistant)
    rs = client.get(f'/api/v1/itinerary/{sid}', params={'user_id': 'u3'})
    assert rs.status_code == 200
    msgs = rs.json()['messages']
    assert len(msgs) >= 2
    assert any(m.get('sender') == 'user' and q in m.get('content', '') for m in msgs)
    assert any(m.get('sender') == 'assistant' for m in msgs)
