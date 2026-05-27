from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.modules.realtime.manager import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/institutes/{institute_id}/planning")
async def planning_websocket(websocket: WebSocket, institute_id: str) -> None:
    await manager.connect(institute_id, websocket)
    try:
        while True:
            # MVP : le client peut envoyer ping, on répond pong.
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(institute_id, websocket)
