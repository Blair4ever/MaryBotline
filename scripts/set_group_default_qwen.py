# scripts/set_group_default_qwen.py
# -------------------------------------------------
# ตั้งค่าโมเดลเริ่มต้นของทุกกลุ่ม (หรือระบุเฉพาะ) ให้ใช้ Qwen 3.5 (GGUF)
#   - default_model, general_conversation_model, summarization_model -> Qwen
#   - tool_execution_model คงเป็น Gemini (เพื่อให้มี tool calling)
# -------------------------------------------------
import asyncio
import sys
from pathlib import Path

# โหลดโฟลเดอร์โปรเจคเป็น PYTHONPATH
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from sqlalchemy import select
from app.database.session import async_session, AsyncSessionLocal
from app.models.group import Group
from app.schemas.group_settings import parse_group_settings, dump_group_settings
from app.services.llm.registry import QWEN35_IQ3_M_FILE


async def set_qwen_for_group(group_id: str | None = None) -> None:
    """ตั้งค่า Qwen เป็นโมเดลเริ่มต้นของกลุ่มที่ระบุหรือของทุกกลุ่ม"""
    async with AsyncSessionLocal() as db:
        if group_id:
            grp = await db.get(Group, group_id)
            groups = [grp] if grp else []
        else:
            result = await db.execute(select(Group))
            groups = result.scalars().all()

        for grp in groups:
            if not grp:
                continue
            settings = parse_group_settings(grp.settings_json)
            # ตั้งค่าโมเดลการสนทนาและสรุปเป็น Qwen3.5 9B The Defiant Fable Uncnr
            settings.default_model = QWEN35_IQ3_M_FILE
            settings.general_conversation_model = QWEN35_IQ3_M_FILE
            settings.summarization_model = QWEN35_IQ3_M_FILE
            # tool execution ยังคงใช้ Gemini เพื่อให้รองรับฟังก์ชันเรียก tools
            settings.tool_execution_model = "gemini-3.5-flash"
            grp.settings_json = dump_group_settings(settings)
            print(f"✅ ตั้งค่า Qwen 3.5 9B (The Defiant Fable Uncnr) ให้กับกลุ่ม {grp.id}")

        await db.commit()
        print("🗃️ อัปเดตกลุ่มทั้งหมดในฐานข้อมูลเรียบร้อยแล้ว")


if __name__ == "__main__":
    # ตัวเลือก: python scripts/set_group_default_qwen.py [GROUP_ID]
    gid = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(set_qwen_for_group(gid))

