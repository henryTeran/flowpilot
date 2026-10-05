from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from anyio import BrokenResourceError, ClosedResourceError


class RealtimeConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, institute_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(institute_id, []).append(websocket)

    def disconnect(self, institute_id: str, websocket: WebSocket) -> None:
        connections = self.active_connections.get(institute_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.active_connections.pop(institute_id, None)

    async def broadcast(self, institute_id: str, event: dict) -> None:
        for connection in tuple(self.active_connections.get(institute_id, [])):
            try:
                await connection.send_json(event)
            except (WebSocketDisconnect, RuntimeError, OSError, BrokenResourceError, ClosedResourceError):
                self.disconnect(institute_id, connection)


manager = RealtimeConnectionManager()
