import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base, GroupScopedMixin, TimestampMixin


class Reminder(Base, GroupScopedMixin, TimestampMixin):
    """Scheduled reminders configured for group delivery."""

    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    creator_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_member_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # None = entire group
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(32), default="once", nullable=False)  # once, daily, weekly, cron
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cron_expression: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, executed, cancelled
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Task(Base, GroupScopedMixin, TimestampMixin):
    """Actionable tasks assigned to group members."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    creator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    assignee_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    assignee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)  # low, medium, high
    status: Mapped[str] = mapped_column(String(32), default="todo", nullable=False)  # todo, in_progress, done, cancelled

