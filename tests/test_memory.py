import pytest
from app.agent.tools.memory_tools import (
    save_group_memory,
    search_group_memories,
    correct_group_memory,
    delete_group_memory,
)


@pytest.mark.asyncio
async def test_memory_lifecycle_and_multi_tenant_isolation(db_session):
    group_a = "group_alpha"
    group_b = "group_beta"

    # 1. Save memory in Group A
    save_res = await save_group_memory(
        group_id=group_a,
        category="factual",
        key="Wifi Password",
        content="SecretPass1234",
        session=db_session,
    )
    assert save_res["success"] is True
    memory_id = save_res["memory_id"]

    # 2. Search in Group A -> should find it
    search_a = await search_group_memories(
        group_id=group_a,
        query="Wifi",
        session=db_session,
    )
    assert len(search_a) == 1
    assert search_a[0]["content"] == "SecretPass1234"

    # 3. Search in Group B -> MUST NOT find Group A's memory (Multi-tenant isolation)
    search_b = await search_group_memories(
        group_id=group_b,
        query="Wifi",
        session=db_session,
    )
    assert len(search_b) == 0

    # 4. Correct memory in Group A
    correct_res = await correct_group_memory(
        group_id=group_a,
        memory_id=memory_id,
        new_content="NewWifiPass9999",
        session=db_session,
    )
    assert correct_res["success"] is True
    assert correct_res["new_content"] == "NewWifiPass9999"

    # 5. Delete memory in Group A
    del_res = await delete_group_memory(
        group_id=group_a,
        memory_id=memory_id,
        session=db_session,
    )
    assert del_res["success"] is True

    # 6. Verify it is no longer returned in search
    search_after_del = await search_group_memories(
        group_id=group_a,
        query="Wifi",
        session=db_session,
    )
    assert len(search_after_del) == 0

