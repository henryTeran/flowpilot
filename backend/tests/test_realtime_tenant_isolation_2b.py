import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token


def _ws_token(role: str = "accueil", institute_id: str | None = None) -> str:
    return create_access_token(
        subject="ws-test-user",
        extra_claims={"role": role, "institute_id": institute_id},
    )


def _bootstrap_institute_id(client) -> str:
    response = client.post("/api/v1/dev/init-demo-data")
    assert response.status_code == 200

    token = _ws_token(role="accueil", institute_id=None)
    institutes = client.get("/api/v1/institutes", headers={"Authorization": f"Bearer {token}"})
    assert institutes.status_code == 200
    return institutes.json()[0]["id"]


def test_planning_websocket_allows_same_institute(client):
    institute_id = _bootstrap_institute_id(client)
    token = _ws_token(role="accueil", institute_id=institute_id)

    with client.websocket_connect(f"/ws/institutes/{institute_id}/planning?token={token}") as ws:
        ws.send_text("ping")
        payload = ws.receive_json()

    assert payload["event"] == "pong"


def test_planning_websocket_blocks_cross_institute(client):
    institute_id = _bootstrap_institute_id(client)
    token = _ws_token(role="accueil", institute_id=f"other-{institute_id}")

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/institutes/{institute_id}/planning?token={token}"):
            pass


def test_planning_websocket_blocks_missing_token(client):
    institute_id = _bootstrap_institute_id(client)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/institutes/{institute_id}/planning"):
            pass
