from datetime import datetime, timedelta, timezone
import pytest
from app.tools.reminders.reminder_tools import create_reminder, list_group_reminders
from app.tools.tasks.task_tools import create_task, list_tasks, update_task_status


@pytest.mark.asyncio
async def test_create_and_list_reminder(db_session):
    group_id = "test_reminder_group_1"
    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    # Create valid reminder
    res = await create_reminder(
        group_id=group_id,
        title="นัดประชุมวางแผน",
        message="อย่าลืมเข้าประชุมทีม 10 โมงนะคะ",
        scheduled_time_iso=future_time,
        session=db_session,
    )
    assert res["success"] is True
    assert "นัดประชุมวางแผน" in res["summary"]

    # List reminders
    list_res = await list_group_reminders(group_id=group_id, session=db_session)
    assert list_res["success"] is True
    assert list_res["count"] == 1
    assert list_res["reminders"][0]["title"] == "นัดประชุมวางแผน"


@pytest.mark.asyncio
async def test_create_reminder_past_time():
    group_id = "test_reminder_group_past"
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    res = await create_reminder(
        group_id=group_id,
        title="อดีต",
        message="ข้อความ",
        scheduled_time_iso=past_time,
    )
    assert res["success"] is False
    assert "อนาคต" in res["error"]


@pytest.mark.asyncio
async def test_task_lifecycle(db_session):
    group_id = "test_task_group_1"

    # 1. Create task
    create_res = await create_task(
        group_id=group_id,
        title="ทำสรุปงบประมาณ",
        assignee_name="สมชาย",
        session=db_session,
    )
    assert create_res["success"] is True
    task_id = create_res["task_id"]
    assert create_res["status"] == "todo"

    # 2. List tasks
    list_res = await list_tasks(group_id=group_id, status="todo", session=db_session)
    assert list_res["success"] is True
    assert list_res["count"] == 1

    # 3. Update task status
    update_res = await update_task_status(
        group_id=group_id,
        task_id=task_id,
        new_status="done",
        session=db_session,
    )
    assert update_res["success"] is True
    assert update_res["new_status"] == "done"

