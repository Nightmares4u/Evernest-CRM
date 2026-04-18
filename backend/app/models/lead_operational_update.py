from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.lead import LeadClosureSource


class LeadOperationalUpdate(Base):
    __tablename__ = "lead_operational_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    calls_made_delta: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    follow_ups_made_delta: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    appointment_booked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    walk_in_happened: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    closed_by: Mapped[LeadClosureSource | None] = mapped_column(
        Enum(
            LeadClosureSource,
            name="lead_closure_source",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    payment_collected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    lead: Mapped["Lead"] = relationship(back_populates="operational_updates")
