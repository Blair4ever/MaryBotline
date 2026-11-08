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


class LineMentionee(BaseModel):
    """Represents an individual mentionee in a LINE message."""
    index: int = 0
    length: int = 0
    type: str = "user"  # "user" or "all"
    userId: Optional[str] = None
    isSelf: Optional[bool] = None


class LineMention(BaseModel):
    """Mention metadata for a LINE message."""
    mentionees: List[LineMentionee] = Field(default_factory=list)


class LineMessageContent(BaseModel):
    """Content of a LINE message event."""

    id: str
    type: str
    text: Optional[str] = None
    mention: Optional[LineMention] = None

    def is_bot_mentioned(self, bot_user_id: Optional[str] = None) -> bool:
        """
        Determines whether the bot was explicitly mentioned in LINE mention metadata.
        Returns True if:
        1. Any mentionee has isSelf is True.
        2. Any mentionee is of type 'all'.
        3. Any mentionee userId matches the configured/discovered bot user ID.
        """
        if not self.mention or not self.mention.mentionees:
            return False
        for m in self.mention.mentionees:
            if m.isSelf is True:
                return True
            if m.type == "all":
                return True
            if bot_user_id and m.userId and m.userId == bot_user_id:
                return True
        return False


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
    destination: Optional[str] = None


class LineWebhookPayload(BaseModel):
    """Top-level webhook payload sent by the LINE platform."""

    destination: Optional[str] = None
    events: List[LineEvent] = Field(default_factory=list)

