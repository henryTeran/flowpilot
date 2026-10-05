import asyncio

from app.modules.realtime.manager import RealtimeConnectionManager


class Socket:
    def __init__(self, failed=False):
        self.failed = failed
        self.messages = []

    async def accept(self):
        pass

    async def send_json(self, value):
        if self.failed:
            raise RuntimeError("Socket closed")
        self.messages.append(value)


def test_dead_connection_does_not_hide_update_from_healthy_clients_or_other_tenant():
    async def scenario():
        manager = RealtimeConnectionManager()
        dead, live, foreign = Socket(True), Socket(), Socket()
        await manager.connect("one", dead)
        await manager.connect("one", live)
        await manager.connect("two", foreign)
        await manager.broadcast("one", {"event": "planning.changed"})
        assert live.messages == [{"event": "planning.changed"}]
        assert foreign.messages == []
        assert manager.active_connections["one"] == [live]
        manager.disconnect("one", live)
        manager.disconnect("one", live)
        assert "one" not in manager.active_connections
        assert manager.active_connections["two"] == [foreign]
    asyncio.run(scenario())
