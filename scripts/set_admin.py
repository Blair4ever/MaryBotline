# scripts/set_admin.py
# -------------------------------------------------
# เพิ่ม / เปลี่ยน role ของสมาชิกในกลุ่มให้เป็น admin
# Usage: python scripts/set_admin.py <GROUP_ID> <USER_ID>
# -------------------------------------------------
import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from app.database.session import async_session, AsyncSessionLocal
from app.models.group import Group, Member
from sqlalchemy import select, update


async def set_admin(group_id: str, user_id: str) -> None:
    async with AsyncSessionLocal() as db:
        # ตรวจสอบกลุ่ม
        group = await db.get(Group, group_id)
        if not group:
            group = Group(id=group_id, is_active=True)
            db.add(group)
            await db.flush()
            print(f"🆕 สร้างกลุ่ม {group_id}")

        # ตรวจสอบสมาชิก
        stmt = select(Member).where(
            Member.group_id == group_id,
            Member.line_user_id == user_id,
        )
        result = await db.execute(stmt)
        member = result.scalar_one_or_none()

        if member:
            await db.execute(
                update(Member)
                .where(Member.id == member.id)
                .values(role="admin")
            )
            print(f"✅ อัปเดต role ของ user '{user_id}' ในกลุ่ม '{group_id}' เป็น admin แล้ว")
        else:
            new_member = Member(
                group_id=group_id,
                line_user_id=user_id,
                display_name=f"Admin_{user_id[:6]}",
                role="admin",
            )
            db.add(new_member)
            print(f"✅ สร้างสมาชิกใหม่ role=admin: user '{user_id}', group '{group_id}'")

        await db.commit()
        print("🗃️ บันทึกเรียบร้อย")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/set_admin.py <GROUP_ID> <USER_ID>")
        sys.exit(1)
    asyncio.run(set_admin(sys.argv[1], sys.argv[2]))

