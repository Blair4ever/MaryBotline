import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import tool_registry
from app.database.session import AsyncSessionLocal
from app.models.conversation import Message

logger = logging.getLogger(__name__)


@tool_registry.register(
    name="get_recent_messages",
    description="Retrieve the recent conversation history in this group to summarize, find context, or extract decisions.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of recent messages to fetch (default: 20, max: 50).",
            },
        },
    },
)
async def get_recent_messages(
    group_id: str,
    limit: int = 20,
    session: Optional[AsyncSession] = None,
) -> List[Dict[str, Any]]:
    """Fetches recent group messages in chronological order."""
    limit = min(max(1, limit), 50)

    async def _execute(db: AsyncSession) -> List[Dict[str, Any]]:
        stmt = (
            select(Message)
            .where(Message.group_id == group_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        messages = list(reversed(result.scalars().all()))

        return [
            {
                "id": m.id,
                "sender_name": m.sender_name or "Anonymous",
                "text": m.text or "",
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)

