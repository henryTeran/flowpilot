from typing import Any


def ok(data: Any = None, message: str = "OK") -> dict[str, Any]:
    return {"success": True, "message": message, "data": data}
