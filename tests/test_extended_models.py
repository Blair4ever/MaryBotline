import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from app.services.llm.client import GeminiLLMClient
from app.services.llm.exceptions import (
    AuthenticationError,
    ConfigurationError,
    EndpointConnectionError,
    ProviderAPIError,
    UnsupportedCapabilityError,
)
from app.services.llm.openai_client import OpenAICompatibleClient
from app.services.llm.registry import (
    QWEN35_DEFIANT_FABLE_GGUF,
    ModelRegistry,
    get_model_registry,
)
from app.services.llm.router import ModelRouter
from app.services.llm.types import (
    AvailabilityStatus,
    CapabilityStatus,
    DeploymentType,
    LLMResponse,
    ModelCapabilityProfile,
    ToolCall,
    WorkloadType,
)


# -------------------------------------------------------------------------
# 1. Custom OpenAI-Compatible Endpoint Connection
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_openai_compatible_endpoint_connection():
    """Verify OpenAI-compatible endpoint client can connect, authenticate, and normalize responses."""
    base_url = "http://localhost:8080/v1"
    api_key = "test-custom-bearer-token"
    model_name = "Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF"

    client = OpenAICompatibleClient(
        base_url=base_url,
        api_key=api_key,
        model=model_name,
        provider_name="self_hosted_gguf",
    )

    mock_response_json = {
        "id": "chatcmpl-test-001",
        "object": "chat.completion",
        "created": 1700000000,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "สวัสดีค่ะ ฉันคือ Qwen3.5 พร้อมช่วยเหลือค่ะ",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 18,
            "completion_tokens": 24,
            "total_tokens": 42,
        },
    }

    mock_resp = httpx.Response(status_code=200, json=mock_response_json)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        messages = [{"role": "user", "content": "สวัสดี"}]
        response = await client.chat_completion(messages=messages)

        assert mock_post.called
        call_kwargs = mock_post.call_args.kwargs
        # Verify Bearer token was sent
        assert call_kwargs["headers"]["Authorization"] == f"Bearer {api_key}"
        # Verify payload structure
        payload = call_kwargs["json"]
        assert payload["model"] == model_name
        assert payload["messages"][0]["content"] == "สวัสดี"

        # Verify normalized LLMResponse
        assert response.content == "สวัสดีค่ะ ฉันคือ Qwen3.5 พร้อมช่วยเหลือค่ะ"
        assert response.finish_reason == "stop"
        assert response.model == model_name
        assert response.provider == "self_hosted_gguf"
        assert response.usage is not None
        assert response.usage.prompt_tokens == 18
        assert response.usage.completion_tokens == 24
        assert response.usage.total_tokens == 42


# -------------------------------------------------------------------------
# 2. Qwen3.5 Model Configuration Profile
# -------------------------------------------------------------------------

def test_qwen35_model_configuration():
    """Verify Qwen3.5-9B fine-tuned GGUF model is properly registered with full capability metadata."""
    registry = get_model_registry()
    profile = registry.get(QWEN35_DEFIANT_FABLE_GGUF)

    assert profile is not None
    assert profile.model_id == QWEN35_DEFIANT_FABLE_GGUF
    assert profile.model_family == "Qwen3.5"
    assert profile.parameters == "9B"
    assert "CapitalSTEEZ47" in profile.source_repo
    assert profile.quantization == "IQ3_M"
    assert "IQ3_M.gguf" in profile.file_name
    assert profile.deployment_type == DeploymentType.GGUF_LOCAL
    assert profile.availability_status == AvailabilityStatus.ACTIVE

    # Fine-tuned uncensored model does not support function calling
    assert profile.tool_calling_support == CapabilityStatus.UNSUPPORTED
    assert profile.is_tool_calling_supported() is False
    assert profile.is_streaming_supported() is True
    assert profile.is_vision_supported() is False
    assert profile.is_reasoning_supported() is True


# -------------------------------------------------------------------------
# 3. Missing Custom Endpoint Configuration
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_custom_endpoint_configuration():
    """Attempting chat completion without a configured base URL raises ConfigurationError."""
    client = OpenAICompatibleClient(base_url="")
    with pytest.raises(ConfigurationError) as exc_info:
        await client.chat_completion(messages=[{"role": "user", "content": "Hi"}])
    assert "base URL is not configured" in str(exc_info.value)


# -------------------------------------------------------------------------
# 4. Invalid Endpoint Credentials
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_endpoint_credentials():
    """HTTP 401/403 responses from custom endpoint trigger AuthenticationError."""
    client = OpenAICompatibleClient(
        base_url="http://localhost:8080/v1",
        api_key="bad-token",
    )
    mock_resp = httpx.Response(
        status_code=401,
        text='{"error": {"message": "Invalid API key provided", "type": "auth_error"}}',
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(AuthenticationError) as exc_info:
            await client.chat_completion(messages=[{"role": "user", "content": "test"}])
        assert "Authentication failed" in str(exc_info.value)


# -------------------------------------------------------------------------
# 5. Unsupported Tool Calling
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unsupported_tool_calling():
    """Attempting tool calling on a model that does not support tools raises UnsupportedCapabilityError."""
    registry = get_model_registry()
    qwen_profile = registry.get(QWEN35_DEFIANT_FABLE_GGUF)

    client = OpenAICompatibleClient(
        base_url="http://localhost:8080/v1",
        model=QWEN35_DEFIANT_FABLE_GGUF,
        capability_profile=qwen_profile,
    )

    dummy_tools = [
        {
            "type": "function",
            "function": {
                "name": "create_task",
                "description": "Create a new task",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        await client.chat_completion(
            messages=[{"role": "user", "content": "ทำภารกิจ"}],
            tools=dummy_tools,
        )
    assert "does not support tool/function calling" in str(exc_info.value)


# -------------------------------------------------------------------------
# 6. Missing Usage Metadata Handling
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_usage_metadata():
    """When endpoint omits usage metadata, response.usage must be None without inventing token counts."""
    client = OpenAICompatibleClient(base_url="http://localhost:8080/v1", model="test-model")

    # Endpoint response without "usage" key
    mock_response_no_usage = {
        "id": "chatcmpl-no-usage",
        "choices": [
            {
                "message": {"role": "assistant", "content": "คำตอบแบบไม่มี usage"},
                "finish_reason": "stop",
            }
        ],
    }
    mock_resp = httpx.Response(status_code=200, json=mock_response_no_usage)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        response = await client.chat_completion(messages=[{"role": "user", "content": "test"}])

        assert response.content == "คำตอบแบบไม่มี usage"
        # Usage must be None, not fabricated numbers!
        assert response.usage is None


# -------------------------------------------------------------------------
# 7. Custom Endpoint Fallback
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_endpoint_fallback():
    """
    When primary custom endpoint fails (connection error), router seamlessly falls back
    to secondary model while preserving complete conversation context.
    """
    router = ModelRouter()

    primary_client = OpenAICompatibleClient(base_url="http://localhost:9999/v1", model="failing-custom")
    fallback_client = MagicMock()
    fallback_client.__class__.__name__ = "MockGeminiFallback"
    fallback_client.chat_completion = AsyncMock(
        return_value=LLMResponse(
            content="Fallback answer from Gemini",
            model="gemini-3.5-flash",
            provider="google",
        )
    )

    conversation_messages = [
        {"role": "user", "content": "คำถามแรก"},
        {"role": "assistant", "content": "คำตอบแรก"},
        {"role": "user", "content": "คำถามที่สอง"},
    ]

    # Primary client raises connection error
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        response = await router.execute_with_fallback(
            primary_client=primary_client,
            fallback_client=fallback_client,
            messages=conversation_messages,
        )

        assert response.content == "Fallback answer from Gemini"
        # Verify fallback received the exact conversation messages context intact
        fallback_client.chat_completion.assert_called_once()
        sent_messages = fallback_client.chat_completion.call_args.kwargs["messages"]
        assert len(sent_messages) == 3
        assert sent_messages[0]["content"] == "คำถามแรก"
        assert sent_messages[2]["content"] == "คำถามที่สอง"


# -------------------------------------------------------------------------
# 8. Model Capability Validation
# -------------------------------------------------------------------------

def test_model_capability_validation():
    """Unknown capabilities must be marked as unknown and NOT automatically treated as supported."""
    registry = ModelRegistry()

    # Register experimental model with unknown capabilities
    exp_model = ModelCapabilityProfile(
        model_id="experimental-uncensored-v1",
        provider="custom",
        model_family="custom",
        tool_calling_support=CapabilityStatus.UNKNOWN,
        vision_support=CapabilityStatus.UNKNOWN,
    )
    registry.register(exp_model)

    # UNKNOWN must NOT evaluate to supported
    assert exp_model.is_tool_calling_supported() is False
    assert exp_model.is_vision_supported() is False
    assert registry.validate_capability("experimental-uncensored-v1", "tool_calling") is False

    # Router must NOT select this model for TOOL_EXECUTION requiring tools
    router = ModelRouter(registry=registry)
    router.set_workload_model(WorkloadType.TOOL_EXECUTION, "experimental-uncensored-v1")

    selected_model, profile = router.select_model_for_operation(
        workload=WorkloadType.TOOL_EXECUTION,
        requires_tools=True,
    )
    # Must have rerouted to tool-capable fallback model
    assert selected_model != "experimental-uncensored-v1"
    assert profile.is_tool_calling_supported() is True


# -------------------------------------------------------------------------
# 9. GGUF Deployment Configuration
# -------------------------------------------------------------------------

def test_gguf_deployment_configuration():
    """Verify GGUF deployment model parameters and local server compatibility."""
    registry = get_model_registry()
    profile = registry.get(QWEN35_DEFIANT_FABLE_GGUF)

    assert profile.deployment_type == DeploymentType.GGUF_LOCAL
    assert profile.context_window == 32768
    assert profile.max_output_tokens == 8192
    assert profile.pricing is None  # Local open-weight inference has no per-token API pricing

    # Can instantiate OpenAICompatibleClient targeting local GGUF server (e.g. llama.cpp / LM Studio)
    local_client = OpenAICompatibleClient(
        base_url="http://localhost:8080/v1",
        model=profile.model_id,
        capability_profile=profile,
    )
    assert local_client._get_chat_url() == "http://localhost:8080/v1/chat/completions"
    assert local_client.profile.deployment_type == DeploymentType.GGUF_LOCAL


# -------------------------------------------------------------------------
# 10. No Duplicate Tool Execution on Fallback
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_duplicate_tool_execution():
    """Fallback execution must never duplicate or re-execute an already completed tool action."""
    router = ModelRouter()

    primary_client = MagicMock()
    primary_client.chat_completion = AsyncMock(
        side_effect=ProviderAPIError("Endpoint error after partial tool execution")
    )

    # Fallback client attempts to request two tool calls:
    # one already executed (call_completed_001) and one new (call_new_002)
    fallback_client = MagicMock()
    fallback_client.chat_completion = AsyncMock(
        return_value=LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(id="call_completed_001", name="create_reminder", arguments={"title": "นัดประชุม"}),
                ToolCall(id="call_new_002", name="send_summary", arguments={"topic": "สรุปงาน"}),
            ],
            model="gemini-3.5-flash",
        )
    )

    already_executed = {"call_completed_001"}

    response = await router.execute_with_fallback(
        primary_client=primary_client,
        fallback_client=fallback_client,
        messages=[{"role": "user", "content": "นัดประชุมและสรุปงาน"}],
        executed_tool_ids=already_executed,
    )

    # Verified: call_completed_001 was filtered out! Only call_new_002 remains!
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "call_new_002"
    assert response.tool_calls[0].name == "send_summary"

