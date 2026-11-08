import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.webhooks.line import process_single_event
from app.models.conversation import Message
from app.models.group import Group
from app.schemas.group_settings import GroupSettings, dump_group_settings
from app.tools.reminders.reminder_tools import create_reminder, execute_scheduled_reminder
from tests.test_security import generate_valid_signature


# -------------------------------------------------------------------------
# Test 7: Signature Verification Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(async_client: AsyncClient):
    """Webhook should reject requests without X-Line-Signature with 403."""
    payload = {"destination": "U12345", "events": []}
    response = await async_client.post("/webhook/line", json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(async_client: AsyncClient):
    """Webhook should reject requests with invalid X-Line-Signature with 403."""
    payload = {"destination": "U12345", "events": []}
    headers = {"X-Line-Signature": "invalid_sig_here"}
    response = await async_client.post("/webhook/line", json=payload, headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_accepts_valid_signature(async_client: AsyncClient):
    """Webhook should accept requests with valid signature and return 200."""
    secret = "test-secret-key-12345"
    payload = {
        "destination": "U12345",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "timestamp": 1620000000000,
                "source": {
                    "type": "group",
                    "groupId": "Cgroup12345",
                    "userId": "Uuser12345",
                },
                "webhookEventId": "01FZ74A0TDDPYRVKNK77XKC3ZR",
                "deliveryContext": {"isRedelivery": False},
                "replyToken": "nHuyWiB7yP5Zw52FIkcQobQuGDXCTA",
                "message": {
                    "id": "325708",
                    "type": "text",
                    "text": "Hello MARY",
                },
            }
        ],
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    valid_sig = generate_valid_signature(body_bytes, secret)

    headers = {
        "X-Line-Signature": valid_sig,
        "Content-Type": "application/json",
    }

    response = await async_client.post("/webhook/line", content=body_bytes, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["events_received"] == 1


# -------------------------------------------------------------------------
# Test 1: Ordinary Group Conversation Produces No Reply (Passive Listening)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ordinary_group_conversation_produces_no_reply(db_session):
    """Ordinary group chat messages must be observed passively without generating an AI reply."""
    event_dict = {
        "type": "message",
        "mode": "active",
        "timestamp": 1620000000000,
        "source": {
            "type": "group",
            "groupId": "Cgroup_passive_001",
            "userId": "Uuser_regular_001",
        },
        "webhookEventId": "EVT_PASSIVE_001",
        "replyToken": "token_passive_001",
        "message": {
            "id": "msg_passive_001",
            "type": "text",
            "text": "วันนี้กินข้าวเที่ยงที่ไหนกันดีครับ",
        },
        "destination": "UBOT12345",
    }

    with patch("app.services.line.client.LineMessagingService.reply_text", new_callable=AsyncMock) as mock_reply:
        await process_single_event(event_dict)
        mock_reply.assert_not_called()

    # Verify message is persisted in database for shared group memory
    stmt = select(Message).where(Message.id == "msg_passive_001")
    res = await db_session.execute(stmt)
    saved_msg = res.scalar_one_or_none()
    assert saved_msg is not None
    assert saved_msg.text == "วันนี้กินข้าวเที่ยงที่ไหนกันดีครับ"


# -------------------------------------------------------------------------
# Test 2: Mentioning MARY Triggers a Response (LINE Mention Metadata)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mentioning_mary_triggers_response():
    """Explicitly mentioning MARY via LINE mention metadata activates response."""
    event_dict = {
        "type": "message",
        "mode": "active",
        "timestamp": 1620000000000,
        "source": {
            "type": "group",
            "groupId": "Cgroup_mention_001",
            "userId": "Uuser_mention_001",
        },
        "webhookEventId": "EVT_MENTION_001",
        "replyToken": "token_mention_001",
        "message": {
            "id": "msg_mention_001",
            "type": "text",
            "text": "@MARY ช่วยสรุปรายการวันนี้หน่อย",
            "mention": {
                "mentionees": [
                    {"index": 0, "length": 5, "type": "user", "userId": "UBOT12345", "isSelf": True}
                ]
            },
        },
        "destination": "UBOT12345",
    }

    with patch("app.agent.orchestrator.AgentOrchestrator.handle_message", new_callable=AsyncMock) as mock_handle:
        mock_handle.return_value = "สรุปรายการเรียบร้อยค่ะ"
        await process_single_event(event_dict)
        mock_handle.assert_called_once()
        call_kwargs = mock_handle.call_args.kwargs
        assert call_kwargs["is_mentioned"] is True


# -------------------------------------------------------------------------
# Test 3: Starting a Message with MARY Triggers a Response
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_starting_message_with_mary_triggers_response():
    """Starting a message with MARY or Mary activates response."""
    event_dict = {
        "type": "message",
        "mode": "active",
        "timestamp": 1620000000000,
        "source": {
            "type": "group",
            "groupId": "Cgroup_prefix_001",
            "userId": "Uuser_prefix_001",
        },
        "webhookEventId": "EVT_PREFIX_001",
        "replyToken": "token_prefix_001",
        "message": {
            "id": "msg_prefix_001",
            "type": "text",
            "text": "Mary รบกวนช่วยสรุปงานเมื่อวานหน่อย",
        },
        "destination": "UBOT12345",
    }

    with patch("app.agent.orchestrator.AgentOrchestrator.handle_message", new_callable=AsyncMock) as mock_handle:
        mock_handle.return_value = "สรุปงานเรียบร้อยค่ะ"
        await process_single_event(event_dict)
        mock_handle.assert_called_once()


# -------------------------------------------------------------------------
# Test 4: Reminder Event Can Trigger Proactive Notification
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reminder_event_can_trigger_proactive_notification(db_session):
    """Proactive messages are sent when a configured reminder event triggers."""
    group_id = "Cgroup_reminder_001"
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    # 1. Ensure group has proactive_notifications enabled (default)
    res = await create_reminder(
        group_id=group_id,
        title="นัดส่งเอกสารโปรเจกต์",
        message="อย่าลืมส่งเอกสารภายใน 12:00 น. นะคะ",
        scheduled_time_iso=future_time,
        session=db_session,
    )
    assert res["success"] is True
    reminder_id = res["reminder_id"]

    # 2. Trigger scheduled reminder execution
    with patch("app.services.line.client.LineMessagingService.push_text", new_callable=AsyncMock) as mock_push:
        mock_push.return_value = True
        success = await execute_scheduled_reminder(reminder_id)
        assert success is True
        mock_push.assert_called_once()
        assert mock_push.call_args.kwargs["to"] == group_id
        assert "นัดส่งเอกสารโปรเจกต์" in mock_push.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_reminder_suppressed_when_proactive_notifications_disabled(db_session):
    """Proactive messages must be suppressed if the group disables proactive_notifications."""
    group_id = "Cgroup_proactive_disabled"

    # Set group settings with proactive_notifications = False
    custom_settings = GroupSettings(proactive_notifications=False)
    group = Group(id=group_id, is_active=True, settings_json=dump_group_settings(custom_settings))
    db_session.add(group)
    await db_session.flush()

    future_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    res = await create_reminder(
        group_id=group_id,
        title="เตือนประชุมลับ",
        message="ข้อความเตือน",
        scheduled_time_iso=future_time,
        session=db_session,
    )
    reminder_id = res["reminder_id"]

    with patch("app.services.line.client.LineMessagingService.push_text", new_callable=AsyncMock) as mock_push:
        success = await execute_scheduled_reminder(reminder_id)
        assert success is False
        mock_push.assert_not_called()


# -------------------------------------------------------------------------
# Test 5: MARY Does Not Respond to Its Own Messages
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mary_does_not_respond_to_own_messages():
    """Messages originating from MARY itself must be ignored."""
    bot_id = "UBOT12345"
    event_dict = {
        "type": "message",
        "mode": "active",
        "timestamp": 1620000000000,
        "source": {
            "type": "group",
            "groupId": "Cgroup_self_001",
            "userId": bot_id,  # From bot itself
        },
        "webhookEventId": "EVT_SELF_001",
        "replyToken": "token_self_001",
        "message": {
            "id": "msg_self_001",
            "type": "text",
            "text": "Mary ping",
        },
        "destination": bot_id,
    }

    with patch("app.services.line.client.LineMessagingService.reply_text", new_callable=AsyncMock) as mock_reply:
        await process_single_event(event_dict)
        mock_reply.assert_not_called()


# -------------------------------------------------------------------------
# Test 6: Duplicate Webhook Events Do Not Produce Duplicate Replies
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_webhook_events_do_not_produce_duplicate_replies():
    """Retried or duplicate webhookEventId must produce at most one reply."""
    event_dict = {
        "type": "message",
        "mode": "active",
        "timestamp": 1620000000000,
        "source": {
            "type": "group",
            "groupId": "Cgroup_dup_001",
            "userId": "Uuser_dup_001",
        },
        "webhookEventId": "EVT_IDEMPOTENCY_UNIQUE_001",
        "replyToken": "token_dup_001",
        "message": {
            "id": "msg_dup_001",
            "type": "text",
            "text": "ping",
        },
        "destination": "UBOT12345",
    }

    with patch("app.services.line.client.LineMessagingService.reply_text", new_callable=AsyncMock) as mock_reply:
        mock_reply.return_value = True

        # First delivery -> replies
        await process_single_event(event_dict)
        assert mock_reply.call_count == 1

        # Second delivery with identical webhookEventId -> ignored
        await process_single_event(event_dict)
        assert mock_reply.call_count == 1


# -------------------------------------------------------------------------
# Test 8: Standby Events Are Not Replied To
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_standby_events_are_not_replied_to():
    """Events in standby mode must be ignored without sending replies."""
    event_dict = {
        "type": "message",
        "mode": "standby",  # Standby mode
        "timestamp": 1620000000000,
        "source": {
            "type": "group",
            "groupId": "Cgroup_standby_001",
            "userId": "Uuser_standby_001",
        },
        "webhookEventId": "EVT_STANDBY_001",
        "replyToken": "token_standby_001",
        "message": {
            "id": "msg_standby_001",
            "type": "text",
            "text": "ping",
        },
        "destination": "UBOT12345",
    }

    with patch("app.services.line.client.LineMessagingService.reply_text", new_callable=AsyncMock) as mock_reply:
        await process_single_event(event_dict)
        mock_reply.assert_not_called()
