from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from sqlalchemy import select

from app.agent.orchestrator import AgentOrchestrator
from app.database.session import AsyncSessionLocal
from app.models.group import Group, Member
from app.schemas.group_settings import parse_group_settings, dump_group_settings, GroupSettings
from app.services.llm.client import GeminiLLMClient
from app.services.llm.commands import handle_model_command
from app.services.llm.exceptions import EndpointConnectionError
from app.services.llm.registry import QWEN35_DEFIANT_FABLE_GGUF, QWEN35_IQ3_M_FILE
from app.services.llm.router import ModelRouter
from app.services.llm.types import LLMResponse, ToolCall, WorkloadType


# -------------------------------------------------------------------------
# 1. Switching between Qwen3.5 and Gemini
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_switching_between_qwen_and_gemini(db_session):
    """Admin can switch conversation model between Qwen3.5 and Gemini dynamically."""
    group_id = "Cgroup_switch_test"
    user_id = "Uadmin_user"

    # Mock custom endpoint to report healthy so switch to Qwen succeeds
    with patch("app.services.llm.openai_client.OpenAICompatibleClient.check_health", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = (True, "Online (Endpoint responsive)")

        # 1. Switch to Qwen
        reply_qwen = await handle_model_command(
            text="/model qwen",
            group_id=group_id,
            user_id=user_id,
            is_admin=True,
            db=db_session,
        )
        assert "สลับโมเดลเริ่มต้นของกลุ่มนี้เรียบร้อยแล้ว" in reply_qwen
        assert "Qwen3.5" in reply_qwen

        # Verify DB updated
        stmt = select(Group).where(Group.id == group_id)
        res = await db_session.execute(stmt)
        group = res.scalar_one()
        settings = parse_group_settings(group.settings_json)
        assert settings.default_model in [QWEN35_IQ3_M_FILE, QWEN35_DEFIANT_FABLE_GGUF]

        # 2. Switch back to Gemini
        reply_gemini = await handle_model_command(
            text="/model gemini",
            group_id=group_id,
            user_id=user_id,
            is_admin=True,
            db=db_session,
        )
        assert "สลับโมเดลเริ่มต้นของกลุ่มนี้เป็น Gemini เรียบร้อยแล้ว" in reply_gemini

        res = await db_session.execute(stmt)
        group = res.scalar_one()
        settings = parse_group_settings(group.settings_json)
        assert settings.default_model == "gemini-3.5-flash"


# -------------------------------------------------------------------------
# 2. Persisting selections after restart
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persisting_selections_after_restart(db_session):
    """Model selection is persisted in SQLite DB and restored per group across sessions."""
    group_a = "Cgroup_persist_alpha"
    group_b = "Cgroup_persist_beta"

    # Set Group A to Qwen3.5
    custom_settings_a = GroupSettings(
        default_model=QWEN35_DEFIANT_FABLE_GGUF,
        general_conversation_model=QWEN35_DEFIANT_FABLE_GGUF,
    )
    group_obj_a = Group(id=group_a, is_active=True, settings_json=dump_group_settings(custom_settings_a))
    db_session.add(group_obj_a)

    # Set Group B to Gemini
    custom_settings_b = GroupSettings(
        default_model="gemini-3.5-flash",
        general_conversation_model="gemini-3.5-flash",
    )
    group_obj_b = Group(id=group_b, is_active=True, settings_json=dump_group_settings(custom_settings_b))
    db_session.add(group_obj_b)
    await db_session.commit()

    # Simulate application restart: load fresh session directly from database
    async with AsyncSessionLocal() as fresh_db:
        res_a = await fresh_db.execute(select(Group).where(Group.id == group_a))
        loaded_a = res_a.scalar_one()
        settings_a = parse_group_settings(loaded_a.settings_json)
        assert settings_a.default_model == QWEN35_DEFIANT_FABLE_GGUF

        res_b = await fresh_db.execute(select(Group).where(Group.id == group_b))
        loaded_b = res_b.scalar_one()
        settings_b = parse_group_settings(loaded_b.settings_json)
        assert settings_b.default_model == "gemini-3.5-flash"


# -------------------------------------------------------------------------
# 3. Unauthorized users cannot change models
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthorized_users_cannot_change_models(db_session):
    """Non-admin members must be rejected when attempting to change models."""
    group_id = "Cgroup_auth_test"
    normal_user_id = "Uregular_member"

    # Attempt to change model with is_admin=False
    reply = await handle_model_command(
        text="/model qwen",
        group_id=group_id,
        user_id=normal_user_id,
        is_admin=False,
        db=db_session,
    )

    assert "เฉพาะผู้ดูแล (Admin)" in reply

    # Verify settings were not changed
    stmt = select(Group).where(Group.id == group_id)
    res = await db_session.execute(stmt)
    group = res.scalar_one_or_none()
    if group and group.settings_json:
        settings = parse_group_settings(group.settings_json)
        assert settings.default_model != QWEN35_DEFIANT_FABLE_GGUF


# -------------------------------------------------------------------------
# 4. Tool execution always selects a compatible model
# -------------------------------------------------------------------------

def test_tool_execution_always_selects_compatible_model():
    """
    Even if Qwen3.5 is set as default model for the group, tool execution workload
    must NEVER select Qwen3.5 (tool-calling unsupported); it must select Gemini.
    """
    router = ModelRouter()
    qwen_group_settings = GroupSettings(
        default_model=QWEN35_DEFIANT_FABLE_GGUF,
        general_conversation_model=QWEN35_DEFIANT_FABLE_GGUF,
        summarization_model=QWEN35_DEFIANT_FABLE_GGUF,
    )

    # 1. General conversation selects Qwen3.5
    selected_conv, profile_conv = router.select_model_for_operation(
        workload=WorkloadType.GENERAL_CONVERSATION,
        requires_tools=False,
        group_settings=qwen_group_settings,
    )
    assert selected_conv in [QWEN35_IQ3_M_FILE, QWEN35_DEFIANT_FABLE_GGUF]

    # 2. Tool execution MUST select tool-capable Gemini
    selected_tool, profile_tool = router.select_model_for_operation(
        workload=WorkloadType.TOOL_EXECUTION,
        requires_tools=True,
        group_settings=qwen_group_settings,
    )
    assert selected_tool == "gemini-3.5-flash"
    assert profile_tool.is_tool_calling_supported() is True


# -------------------------------------------------------------------------
# 5. Fallback behavior
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fallback_behavior_in_orchestrator():
    """
    When primary custom LLM fails with a connection error, orchestrator smoothly
    falls back to Gemini while preserving conversation context.
    """
    mock_primary = MagicMock()
    mock_primary.__class__.__name__ = "OpenAICompatibleClient"
    mock_primary.chat_completion = AsyncMock(
        side_effect=EndpointConnectionError("Connection refused at http://localhost:8080/v1")
    )

    orchestrator = AgentOrchestrator(llm_client=mock_primary)

    with patch("app.services.llm.client.GeminiLLMClient.chat_completion", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = LLMResponse(
            content="คำตอบช่วยเหลือจากโมเดลสำรอง Gemini ค่ะ",
            model="gemini-3.5-flash",
        )

        reply = await orchestrator.handle_message(
            group_id="Cgroup_fallback_orch",
            sender_id="Uuser_test",
            sender_name="Alice",
            text="Mary ช่วยตอบคำถามหน่อย",
            reply_token=None,
            is_group=True,
        )

        assert reply == "คำตอบช่วยเหลือจากโมเดลสำรอง Gemini ค่ะ"
        mock_gemini.assert_called_once()


# -------------------------------------------------------------------------
# 6. Local endpoint unavailable
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_endpoint_unavailable(db_session):
    """
    When local model server is offline, /model qwen refuses to switch and
    reports a clear offline diagnostic message. Never reports connected.
    """
    group_id = "Cgroup_offline_check"

    # Simulate local server being offline (Connection refused)
    with patch("app.services.llm.openai_client.OpenAICompatibleClient.check_health", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = (False, "Offline (Connection refused at http://localhost:8080/v1)")

        reply = await handle_model_command(
            text="/model qwen",
            group_id=group_id,
            user_id="Uadmin",
            is_admin=True,
            db=db_session,
        )

        assert "ไม่สามารถสลับโมเดลเป็น Qwen3.5 ได้ในขณะนี้" in reply
        assert "ออฟไลน์" in reply or "Offline" in reply
        assert "llama.cpp" in reply or "Local Inference" in reply

        # /model status must clearly report offline
        status_reply = await handle_model_command(
            text="/model status",
            group_id=group_id,
            user_id="Uadmin",
            is_admin=True,
            db=db_session,
        )
        assert "❌ ออฟไลน์" in status_reply


# -------------------------------------------------------------------------
# 7. No duplicate tool execution
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_duplicate_tool_execution_in_orchestrator():
    """Already executed tool calls are not re-executed even if model or fallback requests them again."""
    call_1 = ToolCall(id="call_already_run_999", name="create_task", arguments={"title": "ส่งงาน"})
    first_response = LLMResponse(content=None, tool_calls=[call_1])
    second_response = LLMResponse(content="สร้างงานเรียบร้อยแล้วค่ะ")

    mock_llm = MagicMock()
    mock_llm.__class__.__name__ = "MockLLMClient"
    mock_llm.chat_completion = AsyncMock(side_effect=[first_response, second_response])

    orchestrator = AgentOrchestrator(llm_client=mock_llm)

    executed_counts = {"count": 0}

    async def mock_execute_tool(func, group_id, sender_id, args):
        executed_counts["count"] += 1
        return {"success": True, "task_id": "T123"}

    orchestrator._execute_tool = mock_execute_tool

    # Mock tool registry
    mock_tool = MagicMock()
    mock_tool.fn = lambda: None
    with patch("app.tools.tool_registry.get_tool", return_value=mock_tool):
        with patch("app.permissions.PermissionEngine.can_auto_execute", return_value=True):
            reply = await orchestrator.handle_message(
                group_id="Cgroup_dup_tool_test",
                sender_id="Uuser_test",
                sender_name="Alice",
                text="Mary สร้างงานส่งงานให้ที",
                reply_token=None,
                is_group=True,
            )

            assert reply == "สร้างงานเรียบร้อยแล้วค่ะ"
            assert executed_counts["count"] == 1
