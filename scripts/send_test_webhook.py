"""
Simulate an incoming LINE Webhook event locally with authentic HMAC-SHA256 signature.
Usage:
    python scripts/send_test_webhook.py "ping"
    python scripts/send_test_webhook.py "วันนี้กินข้าว 850 บาท 4 คน ฉันจ่ายเอง"
"""
import base64
import hashlib
import hmac
import json
import sys
import uuid
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "REDACTED_CHANNEL_SECRET")
BASE_URL = os.getenv("WEBHOOK_TARGET_URL", "http://localhost:8000/webhooks/line")


def generate_signature(body: bytes, secret: str) -> str:
    hash_digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(hash_digest).decode("utf-8")


def main():
    message_text = sys.argv[1] if len(sys.argv) > 1 else "น้องแมรี่ status"
    event_id = str(uuid.uuid4()).replace("-", "")

    payload = {
        "destination": "U_BOT_DESTINATION",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "timestamp": 1700000000000,
                "source": {
                    "type": "group",
                    "groupId": "C_TEST_GROUP_001",
                    "userId": "U_TEST_USER_ALICE",
                },
                "webhookEventId": event_id,
                "deliveryContext": {"isRedelivery": False},
                "replyToken": f"reply_token_{uuid.uuid4().hex[:12]}",
                "message": {
                    "id": str(uuid.uuid4().int)[:10],
                    "type": "text",
                    "text": message_text,
                },
            }
        ],
    }

    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sig = generate_signature(body_bytes, CHANNEL_SECRET)

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Line-Signature": sig,
    }

    print(f"📡 Sending local test event to {BASE_URL}")
    print(f"💬 Message: '{message_text}'")
    print(f"🔑 Event ID: {event_id}")

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(BASE_URL, content=body_bytes, headers=headers)
            print(f"📥 Status: {resp.status_code}")
            print(f"📄 Response: {resp.text}")
    except httpx.ConnectError:
        print("❌ Could not connect to localhost:8000. Is the server running? (run: .\\scripts\\run_dev.ps1)")


if __name__ == "__main__":
    main()

