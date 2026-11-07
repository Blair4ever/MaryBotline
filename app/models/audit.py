import uuid
from typing import Optional
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base, GroupScopedMixin, TimestampMixin


class AgentAction(Base, GroupScopedMixin, TimestampMixin):
    """Tracks every autonomous action proposed or executed by AURA."""

    __tablename__ = "agent_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    autonomy_level: Mapped[str] = mapped_column(String(8), nullable=False)  # L1, L2, L3
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parameters_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="executed", nullable=False)  # proposed, pending_approval, executed, failed, rejected
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Approval(Base, GroupScopedMixin, TimestampMixin):
    """Workflows requiring explicit group member approval before execution."""

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_actions.id", ondelete="CASCADE"), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, approved, rejected
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AuditLog(Base, GroupScopedMixin, TimestampMixin):
    """Security and compliance audit records."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

