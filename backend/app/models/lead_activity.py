from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.lead import LeadStatus


class LeadActivityLog(Base):
    __tablename__ = "lead_activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    from_status: Mapped[LeadStatus | None] = mapped_column(
        Enum(
            LeadStatus,
            name="lead_status",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    to_status: Mapped[LeadStatus | None] = mapped_column(
        Enum(
            LeadStatus,
            name="lead_status",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    lead: Mapped["Lead"] = relationship(back_populates="activity_logs")
