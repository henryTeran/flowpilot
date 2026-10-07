from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MatrixPage(BaseModel):
    offset: int
    limit: int
    total: int


class MatrixEmployee(BaseModel):
    id: str
    first_name: str
    status: str
    skills: list[str]


class MatrixService(BaseModel):
    id: str
    name: str
    required_skills: list[str]
    requirement_state: Literal["recorded", "none_recorded"]


class MatrixCell(BaseModel):
    employee_id: str
    service_id: str
    meets_recorded_requirements: bool
    missing_skills: list[str]


class SkillMatrixRead(BaseModel):
    institute_id: str
    generated_at: datetime
    employee_page: MatrixPage
    service_page: MatrixPage
    employees: list[MatrixEmployee]
    services: list[MatrixService]
    cells: list[MatrixCell]
