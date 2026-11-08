import abc
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import get_settings
from app.services.llm.exceptions import (
    AuthenticationError,
    ConfigurationError,
    EndpointConnectionError,
    LLMError,
    ProviderAPIError,
    UnsupportedCapabilityError,
)
from app.services.llm.openai_client import OpenAICompatibleClient
from app.services.llm.registry import ModelRegistry, get_model_registry
from app.services.llm.router import ModelRouter
from app.services.llm.types import (
    AvailabilityStatus,
    CapabilityStatus,
    DeploymentType,
    LLMResponse,
    ModelCapabilityProfile,
    ModelPricing,
    TokenUsage,
    ToolCall,
    WorkloadType,
)

logger = logging.getLogger(__name__)


class BaseLLMClient(abc.ABC):
    """Abstract interface for LLM providers."""

    @abc.abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        pass


class GeminiLLMClient(BaseLLMClient):
    """Client for Google Gemini Models (e.g. Gemini 2.5 Flash, Gemini 3.5 Flash)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model or "gemini-3.5-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        if not self.api_key:
            logger.warning("No LLM_API_KEY configured. Returning mock assistant response.")
            return LLMResponse(content="[MARY Dev Mode: LLM_API_KEY not configured]")

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        # Convert standard OpenAI/chat format into Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "system"] else "model"
            contents.append({
                "role": role,
                "parts": [{"text": str(msg.get("content", ""))}]
            })

        body: Dict[str, Any] = {"contents": contents}

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if tools:
            # Format function declarations for Gemini
            func_declarations = []
            for t in tools:
                fn = t.get("function", t)
                func_declarations.append({
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
                })
            body["tools"] = [{"functionDeclarations": func_declarations}]

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        # Parse Gemini response
        response_text = ""
        tool_calls = []

        candidates = data.get("candidates", [])
        if candidates:
            first_candidate = candidates[0]
            content_parts = first_candidate.get("content", {}).get("parts", [])
            for idx, part in enumerate(content_parts):
                if "text" in part:
                    response_text += part["text"]
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append(
                        ToolCall(
                            id=f"call_{idx}",
                            name=fc["name"],
                            arguments=fc.get("args", {}),
                        )
                    )

        # Gemini token counts
        token_usage = None
        usage_meta = data.get("usageMetadata")
        if usage_meta:
            token_usage = TokenUsage(
                prompt_tokens=usage_meta.get("promptTokenCount", 0),
                completion_tokens=usage_meta.get("candidatesTokenCount", 0),
                total_tokens=usage_meta.get("totalTokenCount", 0),
            )

        return LLMResponse(
            content=response_text if response_text else None,
            tool_calls=tool_calls,
            usage=token_usage,
            model=self.model,
            provider="google",
            raw_response=data,
        )


    async def check_health(self) -> tuple[bool, str]:
        """Checks connectivity and credential status of Gemini client."""
        if not self.api_key:
            return False, "LLM_API_KEY not configured"
        return True, "Online (Google Gemini Cloud API configured)"


def get_llm_client(
    workload: WorkloadType = WorkloadType.GENERAL_CONVERSATION,
    group_settings: Optional[Any] = None,
) -> BaseLLMClient:
    """
    Factory to retrieve configured LLM client based on workload, group settings, and availability.
    Enforces capability validation: models lacking required capabilities (e.g. tool execution)
    will automatically route to a capable model.
    """
    settings = get_settings()
    router = ModelRouter()
    requires_tools = (workload == WorkloadType.TOOL_EXECUTION)

    selected_model, profile = router.select_model_for_operation(
        workload=workload,
        requires_tools=requires_tools,
        group_settings=group_settings,
    )

    if profile and profile.provider == "custom":
        return OpenAICompatibleClient(
            base_url=settings.custom_llm_base_url,
            api_key=settings.custom_llm_api_key,
            model=selected_model,
            provider_name=settings.custom_llm_provider_name or "custom_llm",
            capability_profile=profile,
        )

    return GeminiLLMClient(model=selected_model)
