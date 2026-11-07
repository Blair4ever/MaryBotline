import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.event import Event, EventParticipant
from app.tools.base import tool_registry

logger = logging.getLogger(__name__)


@tool_registry.register(
    name="create_event_draft",
    description="Create a draft for a proposed group trip, dinner, or event.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Event or trip title (e.g. 'ทริปเชียงใหม่ 3 วัน 2 คืน', 'งานวันเกิดสมชาย').",
            },
            "destination": {
                "type": "string",
                "description": "Destination city, venue, or location.",
            },
            "description": {
                "type": "string",
                "description": "Summary of activities, dates, or details.",
            },
            "estimated_budget": {
                "type": "number",
                "description": "Estimated total or per-person budget in THB.",
            },
        },
        "required": ["title"],
    },
)
async def create_event_draft(
    group_id: str,
    title: str,
    destination: Optional[str] = None,
    description: Optional[str] = None,
    estimated_budget: Optional[float] = None,
    created_by_user_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Creates a group event draft."""
    budget_dec = Decimal(str(estimated_budget)) if estimated_budget else None

    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        event = Event(
            group_id=group_id,
            title=title,
            destination=destination,
            description=description,
            estimated_budget=budget_dec,
            status="draft",
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        return {
            "success": True,
            "event_id": event.id,
            "title": event.title,
            "destination": event.destination,
            "status": event.status,
            "estimated_budget": float(event.estimated_budget) if event.estimated_budget else None,
            "summary": f"สร้างแบบร่างกิจกรรม '{event.title}' เรียบร้อยแล้วค่ะ สมาชิกสามารถแจ้งยืนยันเข้าร่วมได้เลย",
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)


@tool_registry.register(
    name="rsvp_event",
    description="Record a member's attendance/availability for an event (attending, maybe, declined).",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "ID of the event.",
            },
            "member_name": {
                "type": "string",
                "description": "Name of the responding member.",
            },
            "status": {
                "type": "string",
                "enum": ["attending", "maybe", "declined"],
                "default": "attending",
                "description": "Attendance status.",
            },
        },
        "required": ["event_id", "member_name", "status"],
    },
)
async def rsvp_event(
    group_id: str,
    event_id: str,
    member_name: str,
    status: str = "attending",
    created_by_user_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Records participant RSVP."""
    user_id = created_by_user_id or "unknown_user"

    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        event_stmt = select(Event).where(Event.id == event_id, Event.group_id == group_id)
        res = await db.execute(event_stmt)
        event = res.scalar_one_or_none()
        if not event:
            return {"success": False, "error": f"ไม่พบกิจกรรมรหัส {event_id} ในกลุ่มนี้ค่ะ"}

        # Check existing RSVP
        part_stmt = select(EventParticipant).where(
            EventParticipant.event_id == event_id,
            EventParticipant.group_id == group_id,
            EventParticipant.member_id == user_id,
        )
        part_res = await db.execute(part_stmt)
        participant = part_res.scalar_one_or_none()

        if participant:
            participant.status = status
            participant.member_name = member_name
        else:
            participant = EventParticipant(
                group_id=group_id,
                event_id=event_id,
                member_id=user_id,
                member_name=member_name,
                status=status,
            )
            db.add(participant)

        await db.commit()
        status_th = {"attending": "เข้าร่วมแน่นอน", "maybe": "อาจจะไป", "declined": "ไม่สะดวกไป"}.get(status, status)
        return {
            "success": True,
            "event_title": event.title,
            "member_name": member_name,
            "status": status,
            "summary": f"บันทึกสถานะของคุณ {member_name}: {status_th} สำหรับกิจกรรม '{event.title}' เรียบร้อยค่ะ",
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)


@tool_registry.register(
    name="list_group_events",
    description="List active or upcoming event drafts and trips for this group.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max events to retrieve (default: 5).",
            },
        },
    },
)
async def list_group_events(
    group_id: str,
    limit: int = 5,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Lists group events and participant counts."""
    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        stmt = (
            select(Event)
            .where(Event.group_id == group_id, Event.status != "cancelled")
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        events = result.scalars().all()

        return {
            "success": True,
            "count": len(events),
            "events": [
                {
                    "id": e.id,
                    "title": e.title,
                    "destination": e.destination,
                    "status": e.status,
                    "budget": float(e.estimated_budget) if e.estimated_budget else None,
                }
                for e in events
            ],
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)
