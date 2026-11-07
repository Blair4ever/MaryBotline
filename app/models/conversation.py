import uuid
from typing import Optional
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, GroupScopedMixin, TimestampMixin


class Message(Base, GroupScopedMixin, TimestampMixin):
    """Stores incoming & outgoing messages with idempotency tracking."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # LINE message_id or UUID
    sender_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)  # text, image, sticker, etc.
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    webhook_event_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(16), default="incoming", nullable=False)  # incoming, outgoing

    group: Mapped["Group"] = relationship("Group", back_populates="messages")

