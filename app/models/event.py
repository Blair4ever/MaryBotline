import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, GroupScopedMixin, TimestampMixin


class Event(Base, GroupScopedMixin, TimestampMixin):
    """Represents a planned event, trip, or gathering for a group."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)  # draft, confirmed, cancelled
    itinerary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    participants: Mapped[List["EventParticipant"]] = relationship(
        "EventParticipant", back_populates="event", cascade="all, delete-orphan"
    )


class EventParticipant(Base, GroupScopedMixin, TimestampMixin):
    """Tracks RSVP and availability of members for an event."""

    __tablename__ = "event_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    member_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="attending", nullable=False)  # attending, maybe, declined

    event: Mapped["Event"] = relationship("Event", back_populates="participants")
