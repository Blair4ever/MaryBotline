import inspect
import json
import logging
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import ContextManager
from app.permissions import PermissionEngine
from app.tools import tool_registry
from app.database.session import AsyncSessionLocal
from app.models.audit import AgentAction
from app.models.conversation import Message
from app.services.line.client import LineMessagingService
from app.services.llm.client import BaseLLMClient, GeminiLLMClient, get_llm_client
from app.services.llm.router import ModelRouter
from app.services.llm.types import WorkloadType

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Central orchestration engine for MARY.
    Coordinates context loading, LLM inference, permission validation, tool execution,
    and LINE response dispatch.
    """

    TRIGGER_KEYWORDS = [
        "capri", "คาพริ", "กัปปรี", "@capri", "น้องคาพริ",
        "carpi", "คาร์ปิ", "@carpi", "น้องคาร์ปิ",
        "mary", "แมรี่", "น้องแมรี่", "@mary",
    ]

    def __init__(self, llm_client: Optional[BaseLLMClient] = None, line_service: Optional[LineMessagingService] = None):
        self.llm = llm_client or get_llm_client()
        self.line = line_service or LineMessagingService()

    def should_respond(
        self,
        text: Optional[str],
        is_group: bool,
        is_mentioned: bool = False,
        mention_required: bool = True,
    ) -> bool:
        """
        Determines whether MARY should respond to this message.
        - Direct chats (1-on-1): Always responds.
        - Group chats:
          - If is_mentioned is True: Responds (explicit LINE mention metadata).
          - If message begins with "MARY" or "Mary" or "แมรี่": Responds.
          - If message uses a command (/help, /summary, /tasks, ping, status): Responds.
          - If mention_required is False: Falls back to trigger keywords.
          - Otherwise: Does NOT respond (passive listening default).
        """
        if not is_group:
            return True

        if is_mentioned:
            return True

        if not text:
            return False

        stripped = text.strip()
        lower_text = stripped.lower()

        # Rule B.2: Message begins with "Capri", "คาพริ", "Carpi", "คาร์ปิ", "MARY", "แมรี่"
        if (
            lower_text.startswith("capri")
            or stripped.startswith("คาพริ")
            or lower_text.startswith("carpi")
            or stripped.startswith("คาร์ปิ")
            or lower_text.startswith("mary")
            or stripped.startswith("แมรี่")
        ):
            return True

        # Rule B.3: Configured commands (/help, /summary, /tasks, etc.)
        if stripped.startswith("/") or lower_text in ["ping", "status"]:
            return True

        # If mention is not required by group configuration, fallback to trigger keywords
        if not mention_required:
            return any(keyword in lower_text for keyword in self.TRIGGER_KEYWORDS)

        return False

    async def handle_message(
        self,
        group_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
        reply_token: Optional[str] = None,
        is_group: bool = True,
        is_mentioned: bool = False,
        group_settings: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Main entry point to process an incoming user message.
        """
        mention_required = getattr(group_settings, "mention_required", True) if group_settings else True
        memory_enabled = getattr(group_settings, "memory_enabled", True) if group_settings else True

        if not self.should_respond(
            text=text,
            is_group=is_group,
            is_mentioned=is_mentioned,
            mention_required=mention_required,
        ):
            safe_id = group_id[:4] + "..." + group_id[-4:] if len(group_id) > 8 else "group"
            logger.info(f"Group {safe_id}: Passive listening mode. Silently observing ordinary conversation.")
            return None

        # 1. Build context
        messages = await ContextManager.build_context(
            group_id=group_id,
            current_user_id=sender_id,
            memory_enabled=memory_enabled,
        )

        # 2. Get registered tools
        tools_schema = tool_registry.get_openai_tools_schema()

        # 3. LLM reasoning with Router and Fallback
        router = ModelRouter()
        primary_client = self.llm or get_llm_client(
            workload=WorkloadType.GENERAL_CONVERSATION,
            group_settings=group_settings,
        )
        fallback_client = GeminiLLMClient(model=router.fallback_model_id)

        # Check if active model supports tool calling
        selected_model, profile = router.select_model_for_operation(
            workload=WorkloadType.GENERAL_CONVERSATION,
            requires_tools=False,
            group_settings=group_settings,
        )
        model_supports_tools = profile.is_tool_calling_supported() if profile else True
        effective_tools = tools_schema if (tools_schema and model_supports_tools) else None

        executed_tool_ids: Set[str] = set()

        ai_provider = primary_client.__class__.__name__
        logger.info(f"Invoking AI Orchestrator with provider: {ai_provider} (model: {selected_model})")

        response = await router.execute_with_fallback(
            primary_client=primary_client,
            fallback_client=fallback_client,
            messages=messages,
            tools=effective_tools,
            system_instruction=messages[0]["content"] if messages and messages[0]["role"] == "system" else None,
            executed_tool_ids=executed_tool_ids,
        )

        final_reply_text = response.content or ""

        # 4. Handle tool calls if returned
        if response.tool_calls:
            for tool_call in response.tool_calls:
                # Safeguard: Never execute a previously completed tool call again during fallback/retry
                if tool_call.id in executed_tool_ids:
                    logger.info(f"Skipping duplicate tool call execution: {tool_call.id} ({tool_call.name})")
                    continue
                executed_tool_ids.add(tool_call.id)

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
                    # Use router with fallback for summarizing results
                    second_response = await router.execute_with_fallback(
                        primary_client=primary_client,
                        fallback_client=fallback_client,
                        messages=messages,
                        executed_tool_ids=executed_tool_ids,
                    )
                    final_reply_text = second_response.content or "ดำเนินการเรียบร้อยแล้วค่ะ"

        # 5. Send reply via LINE
        reply_sent = False
        if final_reply_text:
            if reply_token:
                reply_sent = await self.line.reply_text(reply_token=reply_token, text=final_reply_text)
            else:
                reply_sent = await self.line.push_text(to=group_id, text=final_reply_text)

            # Record outgoing bot message in database
            if memory_enabled:
                await self._record_outgoing_message(group_id, final_reply_text)

            logger.info(f"LINE reply dispatch result: success={reply_sent}")

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
        """Stores Carpi's outgoing message in history."""
        import uuid
        async with AsyncSessionLocal() as db:
            msg = Message(
                id=str(uuid.uuid4()),
                group_id=group_id,
                sender_id="CAPRI_AGENT",
                sender_name="Capri",
                message_type="text",
                text=text,
                direction="outgoing",
            )
            db.add(msg)
            await db.commit()

