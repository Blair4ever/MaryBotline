# pytest-asyncio based test for LINE webhook

import json
import hmac
import hashlib
import base64
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings

client = TestClient(app)


def generate_signature(body: bytes, secret: str) -> str:
    secret_clean = secret.strip().strip("'\"")
    digest = hmac.new(secret_clean.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_ping_event_success():
    # Minimal LINE webhook payload with a text message "ping"
    payload = {
        "destination": "U1234567890",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "replyToken": "test-reply-token",
                "timestamp": 0,
                "source": {
                    "type": "user",
                    "userId": "U111111"
                },
                "message": {
                    "id": "msg-1",
                    "type": "text",
                    "text": "ping"
                },
                "webhookEventId": "event-1"
            }
        ]
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    settings = get_settings()
    signature = generate_signature(body_bytes, settings.line_channel_secret)
    headers = {"x-line-signature": signature, "Content-Type": "application/json"}
    response = client.post("/webhooks/line", data=body_bytes, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    # The background task will process the event; we can check that reply was attempted via logs.
    # For simplicity, just ensure no error returned.

# Additional test for invalid signature (should return 403)

def test_invalid_signature():
    payload = {"events": []}
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {"x-line-signature": "invalid", "Content-Type": "application/json"}
    response = client.post("/webhooks/line", data=body_bytes, headers=headers)
    assert response.status_code == 403
