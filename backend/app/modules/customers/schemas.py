from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    display_name: str
    phone: str | None
    created_at: datetime
