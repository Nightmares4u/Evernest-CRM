from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WhatsAppNumber(Base):
    __tablename__ = "whatsapp_numbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey("offices.id"), nullable=False)
    phone_number_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )
    display_phone_number: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    office: Mapped["Office"] = relationship(back_populates="whatsapp_numbers")
    leads: Mapped[list["Lead"]] = relationship(back_populates="whatsapp_number")
