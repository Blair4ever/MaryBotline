import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.scheduler import get_scheduler
from app.database.session import AsyncSessionLocal
from app.models.group import Group
from app.models.reminder import Reminder
from app.schemas.group_settings import parse_group_settings
from app.services.line.client import LineMessagingService
from app.tools.base import tool_registry

logger = logging.getLogger(__name__)


async def execute_scheduled_reminder(reminder_id: str) -> bool:
    """Callback executed by APScheduler when a reminder triggers."""
    async with AsyncSessionLocal() as db:
        stmt = select(Reminder).where(Reminder.id == reminder_id, Reminder.status == "pending")
        result = await db.execute(stmt)
        reminder = result.scalar_one_or_none()

        if not reminder:
            logger.info(f"Reminder {reminder_id} not found or already executed.")
            return False

        # Verify group allows proactive notifications
        group_stmt = select(Group).where(Group.id == reminder.group_id)
        group_res = await db.execute(group_stmt)
        group = group_res.scalar_one_or_none()
        group_settings = parse_group_settings(group.settings_json if group else None)

        if not group_settings.proactive_notifications:
            logger.info(
                f"Proactive notifications disabled for group {reminder.group_id}. "
                f"Suppressing reminder {reminder_id}."
            )
            reminder.status = "suppressed"
            reminder.executed_at = datetime.now(timezone.utc)
            await db.commit()
            return False

        # Send push notification to the LINE group
        line_client = LineMessagingService()
        push_message = (
            f"🔔 [แจ้งเตือนจาก MARY]\n"
            f"📌 เรื่อง: {reminder.title}\n"
            f"💬 รายละเอียด: {reminder.message}"
        )
        if reminder.target_member_id:
            push_message = f"🔔 แจ้งเตือนคุณ @{reminder.target_member_id}\n📌 {reminder.title}\n💬 {reminder.message}"

        success = await line_client.push_text(to=reminder.group_id, text=push_message)

        if success:
            reminder.status = "executed"
            reminder.executed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(f"Executed reminder {reminder_id} in group {reminder.group_id}")
            return True
        return False


@tool_registry.register(
    name="create_reminder",
    description="Schedule a one-time reminder to be sent to the group at a specific future time.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title or topic of the reminder (e.g. 'นัดประชุม', 'กินยา', 'ส่งเอกสาร').",
            },
            "message": {
                "type": "string",
                "description": "The reminder notification body text to send to the group.",
            },
            "scheduled_time_iso": {
                "type": "string",
                "description": "ISO 8601 formatted datetime string for when to alert (e.g. '2026-11-08T10:00:00+07:00' or UTC).",
            },
            "target_member_id": {
                "type": "string",
                "description": "Optional member LINE userId to target/tag specifically.",
            },
        },
        "required": ["title", "message", "scheduled_time_iso"],
    },
)
async def create_reminder(
    group_id: str,
    title: str,
    message: str,
    scheduled_time_iso: str,
    target_member_id: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Creates a reminder and registers an APScheduler date trigger."""
    settings = get_settings()

    try:
        # Parse ISO datetime
        dt = datetime.fromisoformat(scheduled_time_iso)
        if dt.tzinfo is None:
            # Assume local Bangkok time if no timezone offset is provided
            dt = dt.replace(tzinfo=settings.tz)
        dt_utc = dt.astimezone(timezone.utc)
    except Exception as exc:
        return {"success": False, "error": f"Invalid datetime format: {exc}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."}

    now_utc = datetime.now(timezone.utc)
    if dt_utc <= now_utc:
        return {"success": False, "error": "เวลาที่ตั้งเตือนต้องเป็นเวลาในอนาคตค่ะ"}

    creator_id = created_by_user_id or "system"

    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        reminder = Reminder(
            group_id=group_id,
            creator_id=creator_id,
            target_member_id=target_member_id,
            title=title,
            message=message,
            schedule_type="once",
            scheduled_at=dt_utc,
            status="pending",
        )
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)

        # Register with APScheduler
        scheduler = get_scheduler()
        if scheduler and scheduler.running:
            scheduler.add_job(
                execute_scheduled_reminder,
                "date",
                run_date=dt_utc,
                args=[reminder.id],
                id=f"reminder_{reminder.id}",
                replace_existing=True,
            )
            logger.info(f"Scheduled APScheduler job for reminder {reminder.id} at {dt_utc}")

        local_str = dt.astimezone(settings.tz).strftime("%d/%m/%Y เวลา %H:%M น.")
        return {
            "success": True,
            "reminder_id": reminder.id,
            "title": reminder.title,
            "scheduled_time_local": local_str,
            "summary": f"ตั้งเตือน '{title}' ในวันที่ {local_str} เรียบร้อยแล้วค่ะ",
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)


@tool_registry.register(
    name="list_group_reminders",
    description="List active or pending reminders in this group.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max reminders to return (default: 10).",
            },
        },
    },
)
async def list_group_reminders(
    group_id: str,
    limit: int = 10,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieves upcoming reminders for this group."""
    settings = get_settings()

    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        stmt = (
            select(Reminder)
            .where(Reminder.group_id == group_id, Reminder.status == "pending")
            .order_by(Reminder.scheduled_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        reminders = result.scalars().all()

        return {
            "success": True,
            "count": len(reminders),
            "reminders": [
                {
                    "id": r.id,
                    "title": r.title,
                    "message": r.message,
                    "scheduled_at_local": r.scheduled_at.astimezone(settings.tz).strftime("%d/%m/%Y %H:%M"),
                }
                for r in reminders
            ],
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)

