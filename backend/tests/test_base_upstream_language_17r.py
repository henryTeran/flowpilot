from fastapi import HTTPException
from app.modules.base import upstream, plans
from test_base_routes_17b import prepared
from test_base_plans_17d import request
from test_ticket_workflow import _auth_headers
from test_waitlist_matching_15a import NOW


def test_legacy_intent_and_new_plan_require_framework_but_retained_replay_does_not(client, monkeypatch):
    institute, path, invocations = prepared(client, monkeypatch)
    monkeypatch.setattr(plans, "utcnow", lambda: NOW)
    headers = _auth_headers("responsable_institut", institute)
    body = request(invocations[0]).model_dump(mode="json")
    original = client.post(path+"/plans", json=body, headers=headers)
    assert original.status_code == 200, original.text
    def offline(*args): raise HTTPException(503, "private missing BASE dependency")
    monkeypatch.setattr(upstream.OfficialRouter, "resolve", offline)
    response = client.post(path+"/intents/resolve", json=body["intent"], headers=headers)
    assert response.status_code == 502 and "private" not in response.text
    fresh = client.post(path+"/plans", json={**body, "idempotency_key": "fresh-framework-required"}, headers=headers)
    assert fresh.status_code == 502 and "private" not in fresh.text
    recovered = client.post(path+"/plans", json=body, headers=headers)
    assert recovered.status_code == 200 and recovered.json() == original.json()
    assert client.get(path+"/plan-by-key?key=fresh-framework-required", headers=headers).json() is None
