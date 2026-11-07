import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import tool_registry
from app.database.session import AsyncSessionLocal
from app.models.memory import Memory

logger = logging.getLogger(__name__)


@tool_registry.register(
    name="save_group_memory",
    description="Save an important fact, decision, preference, or event to long-term group memory.",
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["factual", "event_decision", "user_preference", "project", "short_term"],
                "description": "The category of memory being saved.",
            },
            "key": {
                "type": "string",
                "description": "A short descriptive title/subject for the memory (e.g. 'Jane food preference', 'Meeting date').",
            },
            "content": {
                "type": "string",
                "description": "The detailed fact, decision, or preference to remember.",
            },
            "expires_in_days": {
                "type": "integer",
                "description": "Optional number of days until this memory expires (e.g. for temporary events).",
            },
        },
        "required": ["category", "key", "content"],
    },
)
async def save_group_memory(
    group_id: str,
    category: str,
    key: str,
    content: str,
    created_by_user_id: Optional[str] = None,
    expires_in_days: Optional[int] = None,
    session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Saves a group memory into the database with multi-tenant scoping."""
    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        memory = Memory(
            group_id=group_id,
            category=category,
            key=key,
            content=content,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
            is_active=True,
        )
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        logger.info(f"Saved memory [{category}] '{key}' for group {group_id}")
        return {
            "success": True,
            "memory_id": memory.id,
            "category": memory.category,
            "key": memory.key,
            "content": memory.content,
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)


@tool_registry.register(
    name="search_group_memories",
    description="Search the group's memory for relevant facts, decisions, preferences, or past events.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword or topic to search for in memories (e.g. 'vegetarian', 'dinner location').",
            },
            "category": {
                "type": "string",
                "enum": ["factual", "event_decision", "user_preference", "project", "short_term"],
                "description": "Optional filter by memory category.",
            },
        },
    },
)
async def search_group_memories(
    group_id: str,
    query: Optional[str] = None,
    category: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> List[Dict[str, Any]]:
    """Retrieve memories belonging strictly to this group."""
    async def _execute(db: AsyncSession) -> List[Dict[str, Any]]:
        stmt = select(Memory).where(
            Memory.group_id == group_id,
            Memory.is_active == True,  # noqa: E712
        )
        if category:
            stmt = stmt.where(Memory.category == category)
        if query:
            search_pattern = f"%{query}%"
            stmt = stmt.where(
                (Memory.key.ilike(search_pattern)) | (Memory.content.ilike(search_pattern))
            )

        now = datetime.now(timezone.utc)
        stmt = stmt.where(
            (Memory.expires_at.is_(None)) | (Memory.expires_at > now)
        ).order_by(Memory.created_at.desc())

        result = await db.execute(stmt)
        memories = result.scalars().all()

        return [
            {
                "id": m.id,
                "category": m.category,
                "key": m.key,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in memories
        ]

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)


@tool_registry.register(
    name="correct_group_memory",
    description="Update or correct an existing group memory when information changes or was inaccurate.",
    parameters={
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "The ID of the memory to update.",
            },
            "new_content": {
                "type": "string",
                "description": "The revised, accurate memory content.",
            },
        },
        "required": ["memory_id", "new_content"],
    },
)
async def correct_group_memory(
    group_id: str,
    memory_id: str,
    new_content: str,
    session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Corrects an existing group memory, enforcing group boundary."""
    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        stmt = select(Memory).where(
            Memory.id == memory_id,
            Memory.group_id == group_id,
            Memory.is_active == True,  # noqa: E712
        )
        result = await db.execute(stmt)
        memory = result.scalar_one_or_none()
        if not memory:
            return {"success": False, "error": f"Memory {memory_id} not found in this group."}

        memory.content = new_content
        await db.commit()
        logger.info(f"Updated memory {memory_id} in group {group_id}")
        return {
            "success": True,
            "memory_id": memory.id,
            "key": memory.key,
            "new_content": memory.content,
        }

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)


@tool_registry.register(
    name="delete_group_memory",
    description="Delete or forget a group memory that is no longer relevant or requested to be removed.",
    parameters={
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "The ID of the memory to delete.",
            },
        },
        "required": ["memory_id"],
    },
)
async def delete_group_memory(
    group_id: str,
    memory_id: str,
    session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Soft deletes or deactivates a group memory within group boundary."""
    async def _execute(db: AsyncSession) -> Dict[str, Any]:
        stmt = select(Memory).where(
            Memory.id == memory_id,
            Memory.group_id == group_id,
        )
        result = await db.execute(stmt)
        memory = result.scalar_one_or_none()
        if not memory:
            return {"success": False, "error": f"Memory {memory_id} not found."}

        memory.is_active = False
        await db.commit()
        logger.info(f"Deactivated memory {memory_id} in group {group_id}")
        return {"success": True, "deleted_memory_id": memory_id}

    if session:
        return await _execute(session)
    async with AsyncSessionLocal() as db:
        return await _execute(db)

