import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.expense import Expense, ExpenseParticipant, Payment
from app.models.group import Member
from app.tools.base import tool_registry

logger = logging.getLogger(__name__)


@tool_registry.register(
    name="calculate_expense_split",
    description="Calculate bill split shares without saving to database (useful for previewing or answering 'คนละกี่บาท').",
    parameters={
        "type": "object",
        "properties": {
            "total_amount": {
                "type": "number",
                "description": "Total expense amount in THB.",
            },
            "participant_count": {
                "type": "integer",
                "description": "Total number of people sharing the bill (including the payer).",
            },
            "payer_name": {
                "type": "string",
                "description": "Name or identifier of the person who paid the total bill.",
            },
        },
        "required": ["total_amount", "participant_count"],
    },
)
async def calculate_expense_split(
    total_amount: float,
    participant_count: int,
    payer_name: Optional[str] = "ผู้จ่าย",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Calculates equal split and individual share amount."""
    if participant_count <= 0:
        return {"success": False, "error": "จำนวนคนต้องมากกว่า 0 ค่ะ"}

    total = Decimal(str(total_amount))
    share = (total / Decimal(participant_count)).quantize(Decimal("0.01"))
    outstanding = total - share  # Amount others owe to the payer

    return {
        "success": True,
        "total_amount": float(total),
        "currency": "THB",
        "participant_count": participant_count,
        "share_per_person": float(share),
        "payer_name": payer_name,
        "outstanding_amount": float(outstanding),
        "summary": f"ยอดรวม {total:,.2f} บาท {participant_count} คน ตกคนละ {share:,.2f} บาท (ยอดค้างจ่ายรวม {outstanding:,.2f} บาท)",
    }


@tool_registry.register(
    name="record_group_expense",
    description="Record a verified group expense into the group ledger and calculate each member's debt.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Description of the expense (e.g. 'มื้อเย็น ชาบู', 'Grab ไปสนามบิน').",
            },
            "total_amount": {
                "type": "number",
                "description": "Total expense amount in THB.",
            },
            "participant_count": {
                "type": "integer",
                "description": "Total number of participants.",
            },
            "split_type": {
                "type": "string",
                "enum": ["equal", "custom", "itemized"],
                "default": "equal",
                "description": "How the bill is divided.",
            },
            "notes": {
                "type": "string",
                "description": "Optional notes or details.",
            },
        },
        "required": ["title", "total_amount", "participant_count"],
    },
)
async def record_group_expense(
    group_id: str,
    title: str,
    total_amount: float,
    participant_count: int,
    split_type: str = "equal",
    notes: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Saves a group expense and records allocated shares."""
    if participant_count <= 0:
        return {"success": False, "error": "จำนวนผู้หารต้องมากกว่า 0 ค่ะ"}

    payer_id = created_by_user_id or "unknown_payer"
    total = Decimal(str(total_amount))
    share = (total / Decimal(participant_count)).quantize(Decimal("0.01"))

    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        # Get payer display name
        member_stmt = select(Member).where(
            Member.group_id == group_id,
            Member.line_user_id == payer_id,
        )
        res = await db.execute(member_stmt)
        member = res.scalar_one_or_none()
        payer_name = member.display_name if member else "ผู้จ่าย"

        # Create Expense
        expense = Expense(
            group_id=group_id,
            title=title,
            total_amount=total,
            currency="THB",
            payer_id=payer_id,
            payer_name=payer_name,
            split_type=split_type,
            notes=notes,
            is_settled=False,
        )
        db.add(expense)
        await db.flush()

        # Add participant record for the payer (marked as paid)
        payer_part = ExpenseParticipant(
            group_id=group_id,
            expense_id=expense.id,
            member_id=payer_id,
            member_name=payer_name,
            share_amount=share,
            is_paid=True,
        )
        db.add(payer_part)

        await db.commit()
        await db.refresh(expense)

        outstanding = total - share
        return {
            "success": True,
            "expense_id": expense.id,
            "title": expense.title,
            "total_amount": float(expense.total_amount),
            "share_per_person": float(share),
            "payer_name": payer_name,
            "participant_count": participant_count,
            "outstanding_amount": float(outstanding),
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)


@tool_registry.register(
    name="get_expense_summary",
    description="Get the summary of recent shared expenses and outstanding balances in this group.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of recent expenses to retrieve (default: 5).",
            },
        },
    },
)
async def get_expense_summary(
    group_id: str,
    limit: int = 5,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieves active expenses and total unsettled amounts."""
    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        stmt = (
            select(Expense)
            .where(Expense.group_id == group_id)
            .order_by(Expense.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        expenses = result.scalars().all()

        unsettled_total = sum(e.total_amount for e in expenses if not e.is_settled)

        return {
            "success": True,
            "unsettled_total": float(unsettled_total),
            "currency": "THB",
            "expenses": [
                {
                    "id": e.id,
                    "title": e.title,
                    "total_amount": float(e.total_amount),
                    "payer_name": e.payer_name,
                    "is_settled": e.is_settled,
                    "created_at": e.created_at.isoformat(),
                }
                for e in expenses
            ],
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)

