import logging
from typing import Any

from fastapi import Request


audit_logger = logging.getLogger("app.audit")


def log_audit_event(
    request: Request,
    current_user: dict[str, str | None],
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_logger.info(
        "Audit event",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "audit_action": action,
            "audit_target_type": target_type,
            "audit_target_id": target_id,
            "audit_actor_sub": current_user.get("sub"),
            "audit_actor_role": current_user.get("role"),
            "audit_institute_id": current_user.get("institute_id"),
            "audit_metadata": metadata or {},
        },
    )
