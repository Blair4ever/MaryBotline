import pytest
from app.tools.expenses.expense_tools import calculate_expense_split, record_group_expense, get_expense_summary


@pytest.mark.asyncio
async def test_calculate_expense_split_exact_spec():
    """
    Specification example:
    'วันนี้กินข้าว 850 บาท 4 คน ฉันจ่ายเอง'
    Expected:
    - Total: 850 THB
    - Participants: 4
    - Per person: 212.50 THB
    - Outstanding: 637.50 THB
    """
    result = await calculate_expense_split(
        total_amount=850.0,
        participant_count=4,
        payer_name="Test User",
    )
    assert result["success"] is True
    assert result["total_amount"] == 850.0
    assert result["participant_count"] == 4
    assert result["share_per_person"] == 212.50
    assert result["outstanding_amount"] == 637.50


@pytest.mark.asyncio
async def test_calculate_expense_split_zero_participants():
    result = await calculate_expense_split(total_amount=500.0, participant_count=0)
    assert result["success"] is False
    assert "มากกว่า 0" in result["error"]


@pytest.mark.asyncio
async def test_record_and_summarize_group_expense(db_session):
    group_id = "test_expense_group_1"
    payer_id = "test_payer_1"

    # Record expense
    record_res = await record_group_expense(
        group_id=group_id,
        title="มื้อเย็น ชาบู",
        total_amount=1200.0,
        participant_count=3,
        created_by_user_id=payer_id,
        session=db_session,
    )
    assert record_res["success"] is True
    assert record_res["share_per_person"] == 400.0
    assert record_res["outstanding_amount"] == 800.0

    # Retrieve summary
    summary_res = await get_expense_summary(
        group_id=group_id,
        session=db_session,
    )
    assert summary_res["success"] is True
    assert summary_res["unsettled_total"] == 1200.0
    assert len(summary_res["expenses"]) == 1
    assert summary_res["expenses"][0]["title"] == "มื้อเย็น ชาบู"

