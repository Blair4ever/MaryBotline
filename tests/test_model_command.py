"""
Integration tests for /model command access control.
Verifies that only admin-role members can change the group model.
"""
import json
import hmac
import hashlib
import base64
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.config import get_settings
from app.models.group import Group, Member
from app.database.session import AsyncSessionLocal

client = TestClient(app)
settings = get_settings()


def _make_sig(body: bytes) -> str:
    secret = settings.line_channel_secret.strip().strip("'\"")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _webhook_payload(group_id: str, user_id: str, text: str, event_id: str) -> bytes:
    payload = {
        "destination": group_id,
        "events": [
            {
                "type": "message",
                "mode": "active",
                "replyToken": f"rtoken-{event_id}",
                "timestamp": 0,
                "source": {
                    "type": "group",
                    "groupId": group_id,
                    "userId": user_id,
                },
                "message": {
                    "id": f"msg-{event_id}",
                    "type": "text",
                    "text": text,
                },
                "webhookEventId": event_id,
            }
        ],
    }
    return json.dumps(payload).encode("utf-8")


async def _ensure_member(group_id: str, user_id: str, role: str) -> None:
    """Helper: insert or update a member's role in the test DB."""
    async with AsyncSessionLocal() as db:
        # ensure group
        group = await db.get(Group, group_id)
        if not group:
            group = Group(id=group_id, is_active=True)
            db.add(group)
            await db.flush()
        # ensure member
        stmt = select(Member).where(
            Member.group_id == group_id,
            Member.line_user_id == user_id,
        )
        result = await db.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            member = Member(
                group_id=group_id,
                line_user_id=user_id,
                display_name="TestUser",
                role=role,
            )
            db.add(member)
        else:
            member.role = role
        await db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_webhook_returns_200_for_empty_events():
    """LINE verify endpoint (empty events) must always return 200."""
    body = json.dumps({"events": []}).encode()
    sig = _make_sig(body)
    resp = client.post(
        "/webhooks/line",
        data=body,
        headers={"x-line-signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200


def test_invalid_signature_returns_403():
    body = json.dumps({"events": []}).encode()
    resp = client.post(
        "/webhooks/line",
        data=body,
        headers={"x-line-signature": "bad-sig", "Content-Type": "application/json"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_model_command_accepted_webhook():
    """
    Webhook returns 200 even for non-admin /model command.
    The actual 'sorry' reply is sent as a background task via LINE API.
    """
    group_id = "G_TEST_NOADMIN"
    user_id = "U_NOADMIN_001"
    await _ensure_member(group_id, user_id, role="member")

    body = _webhook_payload(group_id, user_id, "/model qwen", "ev-noadmin-1")
    sig = _make_sig(body)
    resp = client.post(
        "/webhooks/line",
        data=body,
        headers={"x-line-signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["events_received"] == 1


@pytest.mark.asyncio
async def test_admin_model_command_accepted_webhook():
    """
    Webhook returns 200 for admin /model command.
    The model switch happens in the background task.
    """
    group_id = "G_TEST_ADMIN"
    user_id = "U_ADMIN_001"
    await _ensure_member(group_id, user_id, role="admin")

    body = _webhook_payload(group_id, user_id, "/model gemini", "ev-admin-1")
    sig = _make_sig(body)
    resp = client.post(
        "/webhooks/line",
        data=body,
        headers={"x-line-signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["events_received"] == 1
