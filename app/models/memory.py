import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base, GroupScopedMixin, TimestampMixin


class Memory(Base, GroupScopedMixin, TimestampMixin):
    """Stores shared group memories across short-term, factual, and event categories."""

    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # categories: short_term, factual, event_decision, user_preference, project
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

