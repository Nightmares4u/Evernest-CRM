from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditFlagRule(StrEnum):
    STALE_LEAD = "stale_lead"
    NO_FOLLOW_UP = "no_follow_up"
    INCONSISTENT_STATE = "inconsistent_state"
    UNASSIGNED_ACTIVE_LEAD = "unassigned_active_lead"


class AuditFlagSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class AuditFlag(Base):
    __tablename__ = "audit_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    rule_name: Mapped[AuditFlagRule] = mapped_column(
        Enum(
            AuditFlagRule,
            name="audit_flag_rule",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    severity: Mapped[AuditFlagSeverity] = mapped_column(
        Enum(
            AuditFlagSeverity,
            name="audit_flag_severity",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    lead: Mapped["Lead"] = relationship(back_populates="audit_flags")
