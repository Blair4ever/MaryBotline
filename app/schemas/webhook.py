from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LineSource(BaseModel):
    """Source of a LINE event (user, group, or room)."""

    type: str
    userId: Optional[str] = None
    groupId: Optional[str] = None
    roomId: Optional[str] = None

    @property
    def target_id(self) -> str:
        """Returns the primary target identifier (groupId, roomId, or userId)."""
        return self.groupId or self.roomId or self.userId or "unknown"


class LineMessageContent(BaseModel):
    """Content of a LINE message event."""

    id: str
    type: str
    text: Optional[str] = None


class LineEvent(BaseModel):
    """Represents an individual event received in a LINE webhook."""

    type: str
    mode: Optional[str] = "active"
    timestamp: int
    source: LineSource
    webhookEventId: str
    deliveryContext: Optional[Dict[str, Any]] = None
    replyToken: Optional[str] = None
    message: Optional[LineMessageContent] = None
    postback: Optional[Dict[str, Any]] = None


class LineWebhookPayload(BaseModel):
    """Top-level webhook payload sent by the LINE platform."""

    destination: str
    events: List[LineEvent] = Field(default_factory=list)

