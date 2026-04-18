from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.phone import parse_phone_number
from app.models.lead import LeadClosureSource, LeadStatus


class LeadCreate(BaseModel):
    office_id: int
    full_name: str
    phone: str
    email: str | None = None
    notes: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = parse_phone_number(value)
        if normalized is None:
            raise ValueError("Phone must contain 7 to 15 digits")
        return normalized


class LeadAssign(BaseModel):
    agent_id: int


class LeadStatusUpdate(BaseModel):
    status: LeadStatus


class LeadOperationsUpdate(BaseModel):
    agent_id: int | None = None
    calls_made_increment: int = Field(default=0, ge=0)
    follow_ups_made_increment: int = Field(default=0, ge=0)
    appointment_booked: bool | None = None
    walk_in_happened: bool | None = None
    closed_by: LeadClosureSource | None = None
    payment_collected: bool | None = None
    remarks: str | None = None


class LeadActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    agent_id: int | None
    from_status: LeadStatus | None
    to_status: LeadStatus | None
    created_at: datetime


class LeadOperationalUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int | None
    calls_made_delta: int
    follow_ups_made_delta: int
    appointment_booked: bool | None
    walk_in_happened: bool | None
    closed_by: LeadClosureSource | None
    payment_collected: bool | None
    remarks: str | None
    created_at: datetime


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    office_id: int
    agent_id: int | None
    whatsapp_number_id: int | None
    full_name: str
    phone: str
    email: str | None
    notes: str | None
    calls_made: int
    follow_ups_made: int
    appointment_booked: bool
    walk_in_happened: bool
    closed_by: LeadClosureSource | None
    payment_collected: bool
    remarks: str | None
    status: LeadStatus
    created_at: datetime
    updated_at: datetime


class LeadDetailRead(LeadRead):
    activity_logs: list[LeadActivityLogRead]
    operational_updates: list[LeadOperationalUpdateRead]
