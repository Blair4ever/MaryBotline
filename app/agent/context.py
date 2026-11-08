import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import MARY_SYSTEM_PROMPT
from app.database.session import AsyncSessionLocal
from app.models.conversation import Message
from app.models.group import Member
from app.models.memory import Memory


class ContextManager:
    """Builds rich, multi-tenant scoped conversation context for the AI agent."""

    @classmethod
    async def build_context(
        cls,
        group_id: str,
        current_user_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
        memory_enabled: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Assemble system prompt and recent message history with injected group memories.
        """
        async def _execute(db: AsyncSession) -> List[Dict[str, Any]]:
            # 1. Fetch active group memories (if memory_enabled is True)
            memories_text = ""
            if memory_enabled:
                mem_stmt = (
                    select(Memory)
                    .where(Memory.group_id == group_id, Memory.is_active == True)  # noqa: E712
                    .order_by(Memory.created_at.desc())
                    .limit(10)
                )
                mem_result = await db.execute(mem_stmt)
                memories = mem_result.scalars().all()

                if memories:
                    memories_text = "\n### Current Group Shared Memory:\n"
                    for m in memories:
                        memories_text += f"- [{m.category.upper()}] ({m.key}): {m.content} (id: {m.id})\n"

            # 2. Fetch known group members
            member_stmt = (
                select(Member)
                .where(Member.group_id == group_id, Member.is_active == True)  # noqa: E712
                .limit(20)
            )
            member_result = await db.execute(member_stmt)
            members = member_result.scalars().all()
            members_text = ""
            if members:
                members_text = "\n### Known Group Members:\n"
                for mem in members:
                    members_text += f"- {mem.display_name} (userId: {mem.line_user_id})\n"

            # 3. Assemble full system prompt
            complete_system_prompt = (
                f"{MARY_SYSTEM_PROMPT}\n"
                f"### Group Information:\n"
                f"- Group ID: {group_id}\n"
                f"{members_text}"
                f"{memories_text}"
            )

            # 4. Fetch recent conversation messages
            msg_stmt = (
                select(Message)
                .where(Message.group_id == group_id)
                .order_by(Message.created_at.desc())
                .limit(15)
            )
            msg_result = await db.execute(msg_stmt)
            recent_msgs = list(reversed(msg_result.scalars().all()))

            formatted_messages = [
                {"role": "system", "content": complete_system_prompt}
            ]

            for msg in recent_msgs:
                if not msg.text:
                    continue
                sender_label = msg.sender_name or msg.sender_id or "Member"
                if msg.direction == "outgoing":
                    formatted_messages.append({"role": "model", "content": msg.text})
                else:
                    formatted_messages.append({
                        "role": "user",
                        "content": f"{sender_label}: {msg.text}"
                    })

            return formatted_messages

        if session:
            return await _execute(session)
        async with AsyncSessionLocal() as db:
            return await _execute(db)

