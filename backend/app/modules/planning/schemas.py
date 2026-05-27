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
