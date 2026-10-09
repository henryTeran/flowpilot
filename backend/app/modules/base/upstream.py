"""Bounded stdin bridge to the pinned official BASE broker; no shell or DB access."""
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Literal, Protocol
from pydantic import BaseModel, ConfigDict
from fastapi import HTTPException


class Route(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    status: Literal["routed", "clarification"]
    process_id: str | None
    framework_version: Literal["1.5.1"]
    request_digest: str
    context_prepared: bool


class Router(Protocol):
    def resolve(self, message: str) -> Route: ...


class OfficialRouter:
    def resolve(self, message: str) -> Route:
        script = Path(__file__).resolve().parents[4] / "integrations" / "base" / "runtime.mjs"
        try:
            completed = subprocess.run(
                ["node", str(script)], input=json.dumps({"message": message}),
                capture_output=True, text=True, encoding="utf-8", timeout=15,
                check=True, cwd=script.parent,
            )
            if len(completed.stdout) > 4096:
                raise ValueError("Oversized routing result")
            value = Route.model_validate_json(completed.stdout)
            if value.request_digest != hashlib.sha256(message.encode("utf-8")).hexdigest():
                raise ValueError("Unbound routing result")
            if value.status == "routed" and (not value.process_id or not value.context_prepared):
                raise ValueError("Missing process context")
            return value
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            raise HTTPException(503, "BASE framework unavailable or invalid") from error
