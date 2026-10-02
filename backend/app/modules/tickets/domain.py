"""Walk-in lifecycle policy, independent of persistence and transport."""
from enum import StrEnum


class TicketStatus(StrEnum):
    WAITING = "waiting"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    READY_FOR_CHECKOUT = "ready_for_checkout"
    IN_CHECKOUT = "in_checkout"
    PAID = "paid"
    CANCELLED = "cancelled"


QUEUE_STATUSES = (TicketStatus.WAITING, TicketStatus.ASSIGNED)
ACTIVE_TICKET_STATUSES = (*QUEUE_STATUSES, TicketStatus.IN_PROGRESS,
                          TicketStatus.READY_FOR_CHECKOUT, TicketStatus.IN_CHECKOUT)
TRANSITIONS = {
    "waiting": {"assigned", "in_progress", "cancelled"},
    "assigned": {"waiting", "in_progress", "cancelled"},
    "in_progress": {"ready_for_checkout"},
    "ready_for_checkout": {"in_checkout", "paid", "cancelled"},
    "in_checkout": {"paid", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}


def validate_transition(previous: str, next_status: str) -> None:
    if next_status not in TRANSITIONS.get(previous, set()):
        raise ValueError(f"Invalid ticket transition: {previous} -> {next_status}")


def assignment_state(status: str, employee_id: str | None) -> str:
    if status == "assigned" and employee_id:
        return "assigned"
    if status == "in_progress" and employee_id:
        return "in_service"
    if status in {"ready_for_checkout", "in_checkout", "paid", "completed"}:
        return "completed"
    return "unassigned"
