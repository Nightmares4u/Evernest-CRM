from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import AuditFlagRule, AuditFlagSeverity


class AuditFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    rule_name: AuditFlagRule
    severity: AuditFlagSeverity
    detail: str
    is_active: bool
    detected_at: datetime
    resolved_at: datetime | None


class AuditFlagRecomputeResponse(BaseModel):
    total_leads_checked: int
    active_flags: int
    created_flags: int
    resolved_flags: int
