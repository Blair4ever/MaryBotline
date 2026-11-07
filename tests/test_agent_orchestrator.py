import pytest
from typing import Any, Dict, List, Optional
from app.agent.orchestrator import AgentOrchestrator
from app.services.llm.client import BaseLLMClient, LLMResponse, ToolCall
from app.services.line.client import LineMessagingService


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for deterministic unit testing."""

    def __init__(self, response_text: str = "สวัสดีค่ะ แมรี่พร้อมช่วยค่ะ", tool_calls: Optional[List[ToolCall]] = None):
        self.response_text = response_text
        self.tool_calls = tool_calls or []

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
    ) -> LLMResponse:
        return LLMResponse(
            content=self.response_text,
            tool_calls=self.tool_calls,
        )


def test_agent_orchestrator_should_respond_rules():
    orchestrator = AgentOrchestrator(llm_client=MockLLMClient())

    # Direct 1-on-1 chat always triggers response
    assert orchestrator.should_respond("สวัสดี", is_group=False) is True

    # Group chat: casual greeting should be SILENT (L1 Observe)
    assert orchestrator.should_respond("สวัสดีตอนเช้าครับทุกคน", is_group=True) is False
    assert orchestrator.should_respond("โอเค บ๊ายบาย", is_group=True) is False

    # Group chat: trigger keywords should ACTIVATE
    assert orchestrator.should_respond("น้องแมรี่ ช่วยหน่อย", is_group=True) is True
    assert orchestrator.should_respond("วันนี้กินข้าว 850 บาท หาร 4 คน", is_group=True) is True
    assert orchestrator.should_respond("ช่วยเตือนความจำตอนบ่ายสอง", is_group=True) is True
    assert orchestrator.should_respond("@mary สรุปเมื่อวานให้หน่อย", is_group=True) is True


@pytest.mark.asyncio
async def test_agent_orchestrator_handle_message_with_mock_llm():
    mock_llm = MockLLMClient(response_text="รับทราบค่ะ แมรี่บันทึกเรียบร้อย")
    orchestrator = AgentOrchestrator(llm_client=mock_llm)

    reply = await orchestrator.handle_message(
        group_id="test_group_orch",
        sender_id="user_test_1",
        sender_name="Alice",
        text="แมรี่ สวัสดีจ้า",
        reply_token=None,
        is_group=True,
    )
    assert reply == "รับทราบค่ะ แมรี่บันทึกเรียบร้อย"


@pytest.mark.asyncio
async def test_agent_orchestrator_silent_on_untriggered_message():
    mock_llm = MockLLMClient(response_text="ไม่ควรตอบ")
    orchestrator = AgentOrchestrator(llm_client=mock_llm)

    reply = await orchestrator.handle_message(
        group_id="test_group_orch",
        sender_id="user_test_1",
        sender_name="Alice",
        text="สวัสดีครับทุกคนในกลุ่ม",
        reply_token=None,
        is_group=True,
    )
    assert reply is None
