import asyncio
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.permissions import can_manage_ticket
from app.modules.realtime.manager import manager
from app.modules.realtime import revisions  # noqa: F401 - register transaction hooks
from app.database.session import get_db
from app.modules.realtime.models import PlanningRevision

REVISION_POLL_SECONDS = 1.0


def committed_revision(db, institute_id):
    try:
        return db.scalar(select(PlanningRevision.revision).where(PlanningRevision.institute_id == institute_id)) or 0
    finally:
        # End each read transaction so no stale snapshot or pooled connection is
        # retained for the lifetime of the WebSocket.
        db.rollback()

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
async def planning_websocket(websocket: WebSocket, institute_id: str, db: Session = Depends(get_db)) -> None:
    try:
        current_user = _decode_websocket_user(websocket.query_params.get("token"))
        if current_user.get("institute_id") != institute_id:
            raise HTTPException(status_code=403, detail="Institut non autorise")
    except HTTPException:
        await websocket.close(code=1008)
        return

    revision = await run_in_threadpool(committed_revision, db, institute_id)
    await manager.connect(institute_id, websocket)
    receive = asyncio.create_task(websocket.receive_text())
    next_poll = monotonic() + REVISION_POLL_SECONDS
    try:
        while True:
            ready, _ = await asyncio.wait({receive}, timeout=max(0, next_poll - monotonic()))
            if ready:
                message = receive.result()
                if message == "ping":
                    await websocket.send_json({"event": "pong"})
                receive = asyncio.create_task(websocket.receive_text())
            if monotonic() >= next_poll:
                current = await run_in_threadpool(committed_revision, db, institute_id)
                if current != revision:
                    await websocket.send_json({"event": "planning.changed", "revision": current})
                    revision = current
                next_poll = monotonic() + REVISION_POLL_SECONDS
    except WebSocketDisconnect:
        pass
    finally:
        receive.cancel()
        await asyncio.gather(receive, return_exceptions=True)
        manager.disconnect(institute_id, websocket)
