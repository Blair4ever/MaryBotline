import logging
from typing import Any, Dict, List, Optional
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


class LineMessagingService:
    """Async service to interact with the LINE Messaging API."""

    LINE_API_BASE = "https://api.line.me/v2/bot"

    def __init__(self, channel_access_token: Optional[str] = None) -> None:
        settings = get_settings()
        raw_token = channel_access_token or settings.line_channel_access_token or ""
        self.access_token = raw_token.strip().strip("'\"")
        self._headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def reply_text(self, reply_token: str, text: str) -> bool:
        """Send a plain text reply to a LINE event."""
        if not self.access_token:
            logger.warning(f"[DRY-RUN] LINE reply_text to {reply_token}: {text}")
            return True

        url = f"{self.LINE_API_BASE}/message/reply"
        payload = {
            "replyToken": reply_token,
            "messages": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, headers=self._headers, json=payload)
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as exc:
                resp_text = exc.response.text if exc.response else ""
                logger.error(f"Failed to send LINE reply HTTP {exc.response.status_code}: {resp_text}")
                return False
            except httpx.HTTPError as exc:
                logger.error(f"Failed to send LINE reply: {exc}")
                return False

    async def push_text(self, to: str, text: str) -> bool:
        """Send a proactive push message to a user or group."""
        if not self.access_token:
            logger.warning(f"[DRY-RUN] LINE push_text to {to}: {text}")
            return True

        url = f"{self.LINE_API_BASE}/message/push"
        payload = {
            "to": to,
            "messages": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, headers=self._headers, json=payload)
                response.raise_for_status()
                return True
            except httpx.HTTPError as exc:
                logger.error(f"Failed to send LINE push: {exc}")
                return False

    async def reply_flex(self, reply_token: str, alt_text: str, flex_contents: Dict[str, Any]) -> bool:
        """Send a Flex Message reply to a LINE event."""
        if not self.access_token:
            logger.warning(f"[DRY-RUN] LINE reply_flex to {reply_token}: {alt_text}")
            return True

        url = f"{self.LINE_API_BASE}/message/reply"
        payload = {
            "replyToken": reply_token,
            "messages": [
                {
                    "type": "flex",
                    "altText": alt_text,
                    "contents": flex_contents,
                }
            ],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, headers=self._headers, json=payload)
                response.raise_for_status()
                return True
            except httpx.HTTPError as exc:
                logger.error(f"Failed to send LINE reply_flex: {exc}")
                return False

    async def push_flex(self, to: str, alt_text: str, flex_contents: Dict[str, Any]) -> bool:
        """Send a proactive Flex Message push to a user or group."""
        if not self.access_token:
            logger.warning(f"[DRY-RUN] LINE push_flex to {to}: {alt_text}")
            return True

        url = f"{self.LINE_API_BASE}/message/push"
        payload = {
            "to": to,
            "messages": [
                {
                    "type": "flex",
                    "altText": alt_text,
                    "contents": flex_contents,
                }
            ],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, headers=self._headers, json=payload)
                response.raise_for_status()
                return True
            except httpx.HTTPError as exc:
                logger.error(f"Failed to send LINE push_flex: {exc}")
                return False

    async def get_profile(self, user_id: str, group_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve user profile (display name, picture URL) from group or 1-on-1."""
        if not self.access_token:
            return {"displayName": f"User_{user_id[:6]}", "userId": user_id}

        url = (
            f"{self.LINE_API_BASE}/group/{group_id}/member/{user_id}"
            if group_id
            else f"{self.LINE_API_BASE}/profile/{user_id}"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                logger.error(f"Failed to fetch LINE profile for {user_id}: {exc}")
                return None

