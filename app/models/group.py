import uuid
from typing import List, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class Group(Base, TimestampMixin):
    """Represents a LINE group, multi-person room, or 1-on-1 chat context."""

    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # LINE groupId / roomId / userId
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    picture_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    members: Mapped[List["Member"]] = relationship("Member", back_populates="group", cascade="all, delete-orphan")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="group", cascade="all, delete-orphan")


class Member(Base, TimestampMixin):
    """Represents a group member tracked within a specific group."""

    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id: Mapped[str] = mapped_column(String(64), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    line_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    picture_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="member", nullable=False)  # admin, member
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group: Mapped["Group"] = relationship("Group", back_populates="members")

