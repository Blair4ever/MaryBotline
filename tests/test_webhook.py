import json
import pytest
from httpx import AsyncClient
from tests.test_security import generate_valid_signature


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
                    "text": "Hello AURA",
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

