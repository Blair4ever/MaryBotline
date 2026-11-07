import uuid
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, GroupScopedMixin, TimestampMixin


class Expense(Base, GroupScopedMixin, TimestampMixin):
    """Tracks group expenses, receipts, and split summaries."""

    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    payer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    split_type: Mapped[str] = mapped_column(String(32), default="equal", nullable=False)  # equal, custom, itemized
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_settled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    participants: Mapped[List["ExpenseParticipant"]] = relationship(
        "ExpenseParticipant", back_populates="expense", cascade="all, delete-orphan"
    )


class ExpenseParticipant(Base, GroupScopedMixin, TimestampMixin):
    """Individual member's allocated share for an expense."""

    __tablename__ = "expense_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    expense_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    member_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    share_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    expense: Mapped["Expense"] = relationship("Expense", back_populates="participants")


class Payment(Base, GroupScopedMixin, TimestampMixin):
    """Settlement payment between members."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    to_member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="THB", nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

