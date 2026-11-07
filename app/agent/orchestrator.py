import inspect
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import ContextManager
from app.permissions import PermissionEngine
from app.tools import tool_registry
from app.database.session import AsyncSessionLocal
from app.models.audit import AgentAction
from app.models.conversation import Message
from app.services.line.client import LineMessagingService
from app.services.llm.client import BaseLLMClient, get_llm_client

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Central orchestration engine for MARY.
    Coordinates context loading, LLM inference, permission validation, tool execution,
    and LINE response dispatch.
    """

    TRIGGER_KEYWORDS = [
        "mary", "แมรี่", "น้องแมรี่", "@mary",
        "ช่วย", "สรุป", "หาร", "เคลียร์", "จ่าย",
        "เตือน", "จำ", "โน้ต", "บันทึก", "ลืม",
        "github", "ทริป", "เที่ยว",
    ]

    def __init__(self, llm_client: Optional[BaseLLMClient] = None, line_service: Optional[LineMessagingService] = None):
        self.llm = llm_client or get_llm_client()
        self.line = line_service or LineMessagingService()

    def should_respond(self, text: str, is_group: bool) -> bool:
        """
        Determines whether MARY should proactively respond to this message.
        - Direct chats (1-on-1): Always responds.
        - Group chats: Responds when explicitly called or trigger keywords match.
        """
        if not is_group:
            return True

        if not text:
            return False

        lower_text = text.lower()
        return any(keyword in lower_text for keyword in self.TRIGGER_KEYWORDS)

    async def handle_message(
        self,
        group_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
        reply_token: Optional[str] = None,
        is_group: bool = True,
    ) -> Optional[str]:
        """
        Main entry point to process an incoming user message.
        """
        if not self.should_respond(text, is_group):
            logger.info(f"Message in group {group_id} does not trigger active response. Observing silently.")
            return None

        # 1. Build context
        messages = await ContextManager.build_context(group_id=group_id, current_user_id=sender_id)

        # 2. Get registered tools
        tools_schema = tool_registry.get_openai_tools_schema()

        # 3. LLM reasoning
        response = await self.llm.chat_completion(
            messages=messages,
            tools=tools_schema if tools_schema else None,
            system_instruction=messages[0]["content"] if messages and messages[0]["role"] == "system" else None,
        )

        final_reply_text = response.content or ""

        # 4. Handle tool calls if returned
        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.name
                args = tool_call.arguments
                logger.info(f"LLM requested tool call: {tool_name} with args: {args}")

                # Check security policy
                if not PermissionEngine.can_auto_execute(tool_name):
                    logger.warning(f"Tool {tool_name} requires explicit approval. Halting autonomous execution.")
                    final_reply_text += f"\n⚠️ การกระทำ '{tool_name}' จำเป็นต้องได้รับการยืนยันจากสมาชิกก่อนดำเนินการค่ะ"
                    continue

                tool_def = tool_registry.get_tool(tool_name)
                if not tool_def or not tool_def.fn:
                    logger.error(f"Tool {tool_name} not found in registry.")
                    continue

                # Execute tool safely
                tool_result = await self._execute_tool(tool_def.fn, group_id, sender_id, args)

                # Record in AgentAction audit table
                await self._log_action(group_id, tool_name, args, tool_result)

                # If LLM didn't produce text along with the tool call, invoke LLM once more with tool result
                if not final_reply_text:
                    messages.append({
                        "role": "model",
                        "content": f"[Executed {tool_name}]",
                    })
                    messages.append({
                        "role": "user",
                        "content": f"ผลลัพธ์จาก {tool_name}: {json.dumps(tool_result, ensure_ascii=False)}. กรุณาตอบสรุปให้สมาชิกในกลุ่มทราบอย่างสุภาพและชัดเจน",
                    })
                    second_response = await self.llm.chat_completion(messages=messages)
                    final_reply_text = second_response.content or "ดำเนินการเรียบร้อยแล้วค่ะ"

        # 5. Send reply via LINE
        if final_reply_text:
            if reply_token:
                await self.line.reply_text(reply_token=reply_token, text=final_reply_text)
            else:
                await self.line.push_text(to=group_id, text=final_reply_text)

            # Record outgoing bot message in database
            await self._record_outgoing_message(group_id, final_reply_text)

        return final_reply_text

    async def _execute_tool(
        self,
        func: Any,
        group_id: str,
        sender_id: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Safely invokes a tool with parameter inspection and group context injection."""
        sig = inspect.signature(func)
        call_kwargs = dict(args)

        if "group_id" in sig.parameters:
            call_kwargs["group_id"] = group_id
        if "created_by_user_id" in sig.parameters and "created_by_user_id" not in call_kwargs:
            call_kwargs["created_by_user_id"] = sender_id

        try:
            if inspect.iscoroutinefunction(func):
                return await func(**call_kwargs)
            return func(**call_kwargs)
        except Exception as exc:
            logger.error(f"Tool execution failed for {func.__name__}: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    async def _log_action(
        self,
        group_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Records executed autonomous action to the audit ledger."""
        async with AsyncSessionLocal() as db:
            action = AgentAction(
                group_id=group_id,
                autonomy_level="L3",
                tool_name=tool_name,
                parameters_json=json.dumps(parameters, ensure_ascii=False),
                result_json=json.dumps(result, ensure_ascii=False),
                status="executed" if result.get("success", True) else "failed",
            )
            db.add(action)
            await db.commit()

    async def _record_outgoing_message(self, group_id: str, text: str) -> None:
        """Stores MARY's outgoing message in history."""
        import uuid
        async with AsyncSessionLocal() as db:
            msg = Message(
                id=str(uuid.uuid4()),
                group_id=group_id,
                sender_id="MARY_AGENT",
                sender_name="MARY",
                message_type="text",
                text=text,
                direction="outgoing",
            )
            db.add(msg)
            await db.commit()

