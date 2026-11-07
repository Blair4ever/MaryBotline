import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.session import AsyncSessionLocal
from app.models.reminder import Task
from app.models.group import Member
from app.tools.base import tool_registry

logger = logging.getLogger(__name__)


@tool_registry.register(
    name="create_task",
    description="Assign or create a new task for a group member or the team.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title of the task (e.g. 'ทำสไลด์นำเสนอ', 'จองร้านอาหาร').",
            },
            "description": {
                "type": "string",
                "description": "Detailed requirements or notes.",
            },
            "assignee_name": {
                "type": "string",
                "description": "Name of the person assigned to this task.",
            },
            "deadline_iso": {
                "type": "string",
                "description": "Optional deadline in ISO 8601 format.",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "default": "medium",
            },
        },
        "required": ["title"],
    },
)
async def create_task(
    group_id: str,
    title: str,
    description: Optional[str] = None,
    assignee_name: Optional[str] = None,
    deadline_iso: Optional[str] = None,
    priority: str = "medium",
    created_by_user_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Records a new actionable task."""
    settings = get_settings()
    deadline_dt = None
    if deadline_iso:
        try:
            parsed = datetime.fromisoformat(deadline_iso)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=settings.tz)
            deadline_dt = parsed.astimezone(timezone.utc)
        except Exception:
            pass

    creator_id = created_by_user_id or "system"

    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        task = Task(
            group_id=group_id,
            creator_id=creator_id,
            assignee_name=assignee_name,
            title=title,
            description=description,
            deadline=deadline_dt,
            priority=priority,
            status="todo",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        return {
            "success": True,
            "task_id": task.id,
            "title": task.title,
            "assignee": task.assignee_name or "ยังไม่ระบุ",
            "priority": task.priority,
            "status": task.status,
            "summary": f"บันทึกงาน '{title}' (ผู้รับผิดชอบ: {task.assignee_name or 'ทุกคน'}) เรียบร้อยแล้วค่ะ",
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)


@tool_registry.register(
    name="list_tasks",
    description="List active or pending tasks for this group.",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["all", "todo", "in_progress", "done"],
                "default": "todo",
                "description": "Filter by status.",
            },
        },
    },
)
async def list_tasks(
    group_id: str,
    status: str = "todo",
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieves tasks for this group."""
    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        stmt = select(Task).where(Task.group_id == group_id)
        if status != "all":
            stmt = stmt.where(Task.status == status)

        stmt = stmt.order_by(Task.created_at.desc()).limit(15)
        result = await db.execute(stmt)
        tasks = result.scalars().all()

        return {
            "success": True,
            "count": len(tasks),
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "assignee": t.assignee_name or "ยังไม่ระบุ",
                    "status": t.status,
                    "priority": t.priority,
                }
                for t in tasks
            ],
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)


@tool_registry.register(
    name="update_task_status",
    description="Update the status of a task (e.g. mark done, in_progress, cancelled).",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the task to update.",
            },
            "new_status": {
                "type": "string",
                "enum": ["todo", "in_progress", "done", "cancelled"],
                "description": "New status.",
            },
        },
        "required": ["task_id", "new_status"],
    },
)
async def update_task_status(
    group_id: str,
    task_id: str,
    new_status: str,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Updates a task status."""
    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        stmt = select(Task).where(Task.id == task_id, Task.group_id == group_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            return {"success": False, "error": f"ไม่พบงานรหัส {task_id} ในกลุ่มนี้ค่ะ"}

        task.status = new_status
        await db.commit()

        status_th = {"todo": "รอดำเนินการ", "in_progress": "กำลังทำ", "done": "เสร็จสิ้น", "cancelled": "ยกเลิก"}.get(new_status, new_status)
        return {
            "success": True,
            "task_id": task.id,
            "title": task.title,
            "new_status": task.status,
            "summary": f"อัปเดตงาน '{task.title}' เป็น {status_th} เรียบร้อยแล้วค่ะ",
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)
