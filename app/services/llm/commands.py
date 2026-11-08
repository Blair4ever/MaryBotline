import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.group import Group
from app.schemas.group_settings import parse_group_settings, dump_group_settings
from app.services.llm.client import GeminiLLMClient
from app.services.llm.openai_client import OpenAICompatibleClient
from app.services.llm.registry import QWEN35_DEFIANT_FABLE_GGUF, get_model_registry
from app.services.llm.router import ModelRouter, normalize_model_name
from app.services.llm.types import WorkloadType

logger = logging.getLogger(__name__)


async def handle_model_command(
    text: str,
    group_id: str,
    user_id: str,
    is_admin: bool,
    db: AsyncSession,
) -> Optional[str]:
    """
    Handles administrator model selection and status commands:
    - /model : Show currently selected model
    - /models : List all configured models and availability
    - /model qwen : Switch conversation model to Qwen3.5
    - /model gemini : Switch conversation model to Gemini
    - /model status : Real-time connection and health check
    """
    clean_text = text.strip()
    parts = clean_text.split()
    cmd = parts[0].lower()
    subcmd = parts[1].lower() if len(parts) > 1 else ""

    # Fetch group and settings from database
    group_stmt = select(Group).where(Group.id == group_id)
    group_res = await db.execute(group_stmt)
    group = group_res.scalar_one_or_none()
    if not group:
        group = Group(id=group_id, is_active=True)
        db.add(group)
        await db.flush()

    group_settings = parse_group_settings(group.settings_json)
    settings = get_settings()
    registry = get_model_registry()

    # ---------------------------------------------------------------------
    # 1. /models : List all registered models and capability profiles
    # ---------------------------------------------------------------------
    if cmd == "/models":
        models_list = registry.list_models()
        lines = ["📋 โมเดลที่กำหนดค่าในระบบ MARY:\n"]
        for idx, m in enumerate(models_list, start=1):
            tools_icon = "✅" if m.is_tool_calling_supported() else "❌ (ใช้ Gemini แทน)"
            lines.append(
                f"{idx}. {m.model_family} - {m.model_id[:35]}...\n"
                f"   • Deployment: {m.deployment_type.value}\n"
                f"   • Context: {m.context_window:,} tokens | Output: {m.max_output_tokens:,}\n"
                f"   • Tools: {tools_icon} | Reasoning: {'✅' if m.is_reasoning_supported() else '❌'}\n"
            )
        lines.append(
            "💡 คำสั่งสำหรับผู้ดูแล:\n"
            "• /model qwen : สลับเป็น Qwen3.5 (บทสนทนา/สรุป)\n"
            "• /model gemini : สลับเป็น Gemini (ทุกฟังก์ชัน)\n"
            "• /model status : ตรวจสอบสถานะการเชื่อมต่อแบบสด"
        )
        return "\n".join(lines)

    # ---------------------------------------------------------------------
    # 2. /model status : Check live endpoint health
    # ---------------------------------------------------------------------
    if cmd == "/model" and subcmd == "status":
        lines = ["🔍 ตรวจสอบสถานะการเชื่อมต่อโมเดล (Live Health Check):\n"]

        # Check Gemini
        gemini_client = GeminiLLMClient()
        gemini_ok, gemini_msg = await gemini_client.check_health()
        g_status = "✅ ออนไลน์" if gemini_ok else "❌ ออฟไลน์"
        lines.append(f"1. Google Gemini (Cloud API):\n   สถานะ: {g_status}\n   รายละเอียด: {gemini_msg}\n")

        # Check Custom / Qwen3.5
        custom_client = OpenAICompatibleClient(
            base_url=settings.custom_llm_base_url,
            api_key=settings.custom_llm_api_key,
            model=QWEN35_DEFIANT_FABLE_GGUF,
        )
        custom_ok, custom_msg = await custom_client.check_health()
        c_status = "✅ ออนไลน์" if custom_ok else "❌ ออฟไลน์"
        lines.append(
            f"2. Qwen3.5 9B (Local GGUF / Self-Hosted):\n"
            f"   สถานะ: {c_status}\n"
            f"   รายละเอียด: {custom_msg}\n"
            f"   Endpoint: {settings.custom_llm_base_url or 'ยังไม่ได้ตั้งค่า'}\n"
        )
        lines.append("🛡️ หมายเหตุ: ไม่มีการแสดงผล Token หรือความลับใดๆ ในรายงานนี้")
        return "\n".join(lines)

    # ---------------------------------------------------------------------
    # 3. /model qwen : Switch conversation model to Qwen3.5 (Admin only)
    # ---------------------------------------------------------------------
    if cmd == "/model" and subcmd in ["qwen", "qwen3.5"]:
        if not is_admin:
            return "⚠️ ขออภัยค่ะ เฉพาะผู้ดูแล (Admin) ของกลุ่มเท่านั้นที่สามารถเปลี่ยนการตั้งค่าโมเดลได้ค่ะ"

        # Check availability before selecting
        custom_client = OpenAICompatibleClient(
            base_url=settings.custom_llm_base_url,
            api_key=settings.custom_llm_api_key,
            model=QWEN35_DEFIANT_FABLE_GGUF,
        )
        is_healthy, status_msg = await custom_client.check_health()
        if not is_healthy and "Offline" in status_msg:
            return (
                f"❌ ไม่สามารถสลับโมเดลเป็น Qwen3.5 ได้ในขณะนี้\n"
                f"📡 สถานะ: {status_msg}\n"
                f"💡 คำแนะนำ: กรุณาเปิดเครื่องแม่ข่าย Local Inference (เช่น llama.cpp server, Ollama, หรือ LM Studio) "
                f"ที่ {settings.custom_llm_base_url or 'CUSTOM_LLM_BASE_URL'} ก่อนค่ะ"
            )

        # Update group settings in database
        group_settings.default_model = QWEN35_DEFIANT_FABLE_GGUF
        group_settings.general_conversation_model = QWEN35_DEFIANT_FABLE_GGUF
        group_settings.summarization_model = QWEN35_DEFIANT_FABLE_GGUF
        # Rule 3: Never route tool execution to Qwen3.5 (remains Gemini)
        group_settings.tool_execution_model = "gemini-3.5-flash"

        group.settings_json = dump_group_settings(group_settings)
        await db.commit()

        return (
            "✅ สลับโมเดลเริ่มต้นของกลุ่มนี้เรียบร้อยแล้วค่ะ!\n\n"
            "🤖 โมเดลการสนทนา & สรุป: Qwen3.5 (9B GGUF Fine-Tuned)\n"
            "🛠️ โมเดลการเรียก Tool & Function: Gemini 3.5 Flash (Verified Tool Calling)\n"
            "💾 บันทึกการตั้งค่าลงฐานข้อมูลเรียบร้อย (มีผลถาวรแม้เริ่มระบบใหม่)"
        )

    # ---------------------------------------------------------------------
    # 4. /model gemini : Switch conversation model to Gemini (Admin only)
    # ---------------------------------------------------------------------
    if cmd == "/model" and subcmd in ["gemini", "google"]:
        if not is_admin:
            return "⚠️ ขออภัยค่ะ เฉพาะผู้ดูแล (Admin) ของกลุ่มเท่านั้นที่สามารถเปลี่ยนการตั้งค่าโมเดลได้ค่ะ"

        group_settings.default_model = "gemini-3.5-flash"
        group_settings.general_conversation_model = "gemini-3.5-flash"
        group_settings.reasoning_model = "gemini-3.5-flash"
        group_settings.summarization_model = "gemini-2.5-flash"
        group_settings.tool_execution_model = "gemini-3.5-flash"

        group.settings_json = dump_group_settings(group_settings)
        await db.commit()

        return (
            "✅ สลับโมเดลเริ่มต้นของกลุ่มนี้เป็น Gemini เรียบร้อยแล้วค่ะ!\n\n"
            "🤖 โมเดลหลัก: Gemini 3.5 Flash (Google Cloud API)\n"
            "🛠️ ทุกฟังก์ชัน (สนทนา, สรุป, ใช้เหตุผล, เรียก Tool) ทำงานเต็มรูปแบบ\n"
            "💾 บันทึกการตั้งค่าลงฐานข้อมูลเรียบร้อย"
        )

    # ---------------------------------------------------------------------
    # 5. /model : Show currently selected model
    # ---------------------------------------------------------------------
    if cmd == "/model" and not subcmd:
        conv_model = (
            group_settings.general_conversation_model
            or group_settings.default_model
            or settings.llm_model
            or "gemini-3.5-flash"
        )
        tool_model = group_settings.tool_execution_model or "gemini-3.5-flash"
        summ_model = group_settings.summarization_model or conv_model

        short_conv = "Qwen3.5 (9B GGUF)" if "qwen" in conv_model.lower() else conv_model
        short_tool = "Gemini 3.5 Flash (Verified Tools)" if "gemini" in tool_model.lower() else tool_model

        return (
            f"🤖 การตั้งค่าโมเดลปัจจุบันของกลุ่มนี้:\n\n"
            f"• สนทนาทั่วไป: {short_conv}\n"
            f"• การเรียกใช้ Tool: {short_tool}\n"
            f"• การสรุปข้อความ: {'Qwen3.5' if 'qwen' in summ_model.lower() else summ_model}\n"
            f"• สถานะ: บันทึกในฐานข้อมูลแยกรายกลุ่มเรียบร้อย\n\n"
            f"💡 สลับโมเดล: พิมพ์ /model qwen หรือ /model gemini"
        )

    return None
