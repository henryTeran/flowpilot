from datetime import datetime

from pydantic import BaseModel


class InstituteDashboardRead(BaseModel):
    institute_id: str
    generated_at: datetime

    employees_total: int
    employees_available: int
    employees_busy: int
    employees_delayed: int
    employees_pause: int
    employees_absent_or_offline: int

    tickets_waiting: int
    tickets_assigned: int
    tickets_in_progress: int
    tickets_completed_today: int
    tickets_cancelled_today: int

    sessions_active: int
    sessions_delayed: int
    sessions_completed_today: int

    average_wait_minutes: int | None
    next_available_employee_name: str | None
    next_available_minutes: int | None

    operational_status: str
    alert_message: str | None
