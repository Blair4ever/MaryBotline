import json
import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GroupSettings(BaseModel):
    """
    Configurable group behavior settings with secure defaults.
    - passive_listening: True -> MARY silently observes ordinary conversation.
    - mention_required: True -> Only respond when mentioned or command invoked.
    - proactive_notifications: True -> Allow reminders/deadline notifications.
    - memory_enabled: True -> Store context and memories for group.
    """
    passive_listening: bool = Field(default=True, description="Passive listening enabled")
    mention_required: bool = Field(default=True, description="Only activate when mentioned or command")
    proactive_notifications: bool = Field(default=True, description="Allow proactive reminders/notifications")
    memory_enabled: bool = Field(default=True, description="Enable shared group memory")


def parse_group_settings(settings_json: Optional[str]) -> GroupSettings:
    """Parse JSON string into GroupSettings or return defaults."""
    if not settings_json:
        return GroupSettings()
    try:
        data = json.loads(settings_json)
        if isinstance(data, dict):
            return GroupSettings(**data)
    except Exception as exc:
        logger.warning(f"Error parsing group settings: {exc}")
    return GroupSettings()


def dump_group_settings(settings: GroupSettings) -> str:
    """Serialize GroupSettings to JSON string."""
    return settings.model_dump_json()

