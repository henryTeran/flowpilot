from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.core.config import settings
from app.core.permissions import can_manage_ticket, require_same_institute
from app.modules.realtime.manager import manager

router = APIRouter(tags=["realtime"])


def _decode_websocket_user(token: str | None) -> dict[str, str | None]:
    if not token:
        raise HTTPException(status_code=403, detail="Token manquant")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=403, detail="Token invalide") from exc

    role = payload.get("role")
    if role is None or not can_manage_ticket(str(role)):
        raise HTTPException(status_code=403, detail="Permission insuffisante")

    return {
        "role": str(role),
        "institute_id": payload.get("institute_id"),
        "sub": payload.get("sub"),
    }


@router.websocket("/ws/institutes/{institute_id}/planning")
async def planning_websocket(websocket: WebSocket, institute_id: str) -> None:
    try:
        current_user = _decode_websocket_user(websocket.query_params.get("token"))
        require_same_institute(current_user, institute_id)
    except HTTPException:
        await websocket.close(code=1008)
        return

    await manager.connect(institute_id, websocket)
    try:
        while True:
            # MVP : le client peut envoyer ping, on répond pong.
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(institute_id, websocket)
