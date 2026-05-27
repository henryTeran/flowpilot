from fastapi import WebSocket


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

    async def broadcast(self, institute_id: str, event: dict) -> None:
        for connection in self.active_connections.get(institute_id, []):
            await connection.send_json(event)


manager = RealtimeConnectionManager()
