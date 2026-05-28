from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StartSession(BaseModel):
    ticket_id: str
    employee_id: str
    service_id: str


class ExtendSession(BaseModel):
    minutes: int = Field(ge=5, le=60)


class ServiceSessionRead(BaseModel):
    id: str
    ticket_line_id: str | None
    institute_id: str
    employee_id: str
    service_id: str
    start_time: datetime
    planned_end_time: datetime
    real_end_time: datetime | None
    duration_minutes: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class PlanningEmployeeRow(BaseModel):
    employee_id: str
    employee_name: str
    employee_status: str
    sessions: list[ServiceSessionRead]


class PlanningDayRead(BaseModel):
    institute_id: str
    generated_at: datetime
    rows: list[PlanningEmployeeRow]


class AvailabilityEmployeeRead(BaseModel):
    employee_id: str
    employee_name: str
    employee_status: str
    available_at: datetime | None
    wait_minutes: int | None
    active_session_id: str | None = None


class PlanningAvailabilityRead(BaseModel):
    institute_id: str
    generated_at: datetime
    next_employee_id: str | None
    next_employee_name: str | None
    next_available_at: datetime | None
    wait_minutes: int | None
    active_sessions: int
    waiting_tickets: int
    employees: list[AvailabilityEmployeeRead]
