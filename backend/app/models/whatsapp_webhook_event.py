from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WhatsAppWebhookEvent(Base):
    __tablename__ = "whatsapp_webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    object_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(30),
        default="received",
        server_default="received",
        nullable=False,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
