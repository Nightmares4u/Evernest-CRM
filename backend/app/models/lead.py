from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LeadStatus(StrEnum):
    NEW = "new"
    ASSIGNED = "assigned"
    CONTACTED = "contacted"
    FOLLOW_UP = "follow_up"
    APPOINTMENT_BOOKED = "appointment_booked"
    WALK_IN_DONE = "walk_in_done"
    QUALIFIED = "qualified"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    NO_RESPONSE = "no_response"


ALLOWED_LEAD_STATUS_TRANSITIONS: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.NEW: {
        LeadStatus.ASSIGNED,
        LeadStatus.CLOSED_LOST,
        LeadStatus.NO_RESPONSE,
    },
    LeadStatus.ASSIGNED: {
        LeadStatus.CONTACTED,
        LeadStatus.CLOSED_LOST,
        LeadStatus.NO_RESPONSE,
    },
    LeadStatus.CONTACTED: {
        LeadStatus.FOLLOW_UP,
        LeadStatus.APPOINTMENT_BOOKED,
        LeadStatus.QUALIFIED,
        LeadStatus.CLOSED_LOST,
        LeadStatus.NO_RESPONSE,
    },
    LeadStatus.FOLLOW_UP: {
        LeadStatus.CONTACTED,
        LeadStatus.APPOINTMENT_BOOKED,
        LeadStatus.QUALIFIED,
        LeadStatus.CLOSED_LOST,
        LeadStatus.NO_RESPONSE,
    },
    LeadStatus.APPOINTMENT_BOOKED: {
        LeadStatus.WALK_IN_DONE,
        LeadStatus.QUALIFIED,
        LeadStatus.CLOSED_LOST,
        LeadStatus.NO_RESPONSE,
    },
    LeadStatus.WALK_IN_DONE: {
        LeadStatus.QUALIFIED,
        LeadStatus.CLOSED_WON,
        LeadStatus.CLOSED_LOST,
    },
    LeadStatus.QUALIFIED: {
        LeadStatus.CLOSED_WON,
        LeadStatus.CLOSED_LOST,
    },
    LeadStatus.NO_RESPONSE: {
        LeadStatus.CONTACTED,
        LeadStatus.FOLLOW_UP,
        LeadStatus.CLOSED_LOST,
    },
    LeadStatus.CLOSED_WON: set(),
    LeadStatus.CLOSED_LOST: set(),
}


def can_transition_lead_status(
    current_status: LeadStatus,
    next_status: LeadStatus,
) -> bool:
    return next_status in ALLOWED_LEAD_STATUS_TRANSITIONS[current_status]


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey("offices.id"), nullable=False)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(
            LeadStatus,
            name="lead_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=LeadStatus.NEW,
        server_default=LeadStatus.NEW.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    office: Mapped["Office"] = relationship(back_populates="leads")
    agent: Mapped["Agent | None"] = relationship(back_populates="leads")
    activity_logs: Mapped[list["LeadActivityLog"]] = relationship(
        back_populates="lead",
        order_by="LeadActivityLog.created_at",
    )
