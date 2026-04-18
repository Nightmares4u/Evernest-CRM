from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.lead import LeadStatus


class LeadCreate(BaseModel):
    office_id: int
    full_name: str
    phone: str
    email: str | None = None
    notes: str | None = None


class LeadAssign(BaseModel):
    agent_id: int


class LeadStatusUpdate(BaseModel):
    status: LeadStatus


class LeadActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    agent_id: int | None
    from_status: LeadStatus | None
    to_status: LeadStatus | None
    created_at: datetime


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    office_id: int
    agent_id: int | None
    full_name: str
    phone: str
    email: str | None
    notes: str | None
    status: LeadStatus
    created_at: datetime
    updated_at: datetime


class LeadDetailRead(LeadRead):
    activity_logs: list[LeadActivityLogRead]
