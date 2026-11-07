import pytest
from app.tools.travel.travel_tools import create_event_draft, rsvp_event, list_group_events


@pytest.mark.asyncio
async def test_event_and_rsvp_lifecycle(db_session):
    group_id = "test_event_group_1"

    # 1. Create event draft
    draft_res = await create_event_draft(
        group_id=group_id,
        title="ทริปเขาใหญ่ 2 วัน 1 คืน",
        destination="เขาใหญ่ นครราชสีมา",
        estimated_budget=3500.0,
        session=db_session,
    )
    assert draft_res["success"] is True
    event_id = draft_res["event_id"]
    assert draft_res["destination"] == "เขาใหญ่ นครราชสีมา"

    # 2. RSVP for event
    rsvp_res = await rsvp_event(
        group_id=group_id,
        event_id=event_id,
        member_name="บอย",
        status="attending",
        created_by_user_id="user_boy",
        session=db_session,
    )
    assert rsvp_res["success"] is True
    assert rsvp_res["status"] == "attending"

    # 3. List group events
    list_res = await list_group_events(group_id=group_id, session=db_session)
    assert list_res["success"] is True
    assert list_res["count"] == 1
    assert list_res["events"][0]["title"] == "ทริปเขาใหญ่ 2 วัน 1 คืน"
