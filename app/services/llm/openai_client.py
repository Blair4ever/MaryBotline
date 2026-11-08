import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from app.config import get_settings
from app.services.llm.exceptions import (
    AuthenticationError,
    ConfigurationError,
    EndpointConnectionError,
    ProviderAPIError,
    UnsupportedCapabilityError,
)
from app.services.llm.registry import get_model_registry
from app.services.llm.types import (
    LLMResponse,
    ModelCapabilityProfile,
    TokenUsage,
    ToolCall,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    """
    OpenAI-compatible endpoint adapter supporting custom fine-tuned models,
    self-hosted GGUF engines (llama.cpp, Ollama, LM Studio, vLLM),
    and third-party OpenAI-compatible inference providers.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider_name: Optional[str] = None,
        timeout: float = 60.0,
        capability_profile: Optional[ModelCapabilityProfile] = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.custom_llm_base_url or "").rstrip("/")
        self.api_key = api_key if api_key is not None else settings.custom_llm_api_key
        self.model = model or settings.custom_llm_model or "custom-model"
        self.provider_name = provider_name or settings.custom_llm_provider_name or "custom_openai_compatible"
        self.timeout = timeout

        # Resolve or fetch capability profile from registry
        if capability_profile:
            self.profile = capability_profile
        else:
            registry = get_model_registry()
            self.profile = registry.get(self.model)

    def _build_headers(self) -> Dict[str, str]:
        """Constructs headers including Bearer auth token if configured."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MARY-Bot-LLMClient/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_chat_url(self) -> str:
        """Determines the chat completions URL from base_url."""
        if not self.base_url:
            raise ConfigurationError(
                "Custom LLM base URL is not configured. Set CUSTOM_LLM_BASE_URL in environment."
            )
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def _validate_capabilities(self, tools: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Validates whether the model/endpoint supports the requested operations.
        Raises UnsupportedCapabilityError if tool calling is requested on an unsupported model.
        """
        if tools:
            if self.profile and not self.profile.is_tool_calling_supported():
                raise UnsupportedCapabilityError(
                    f"Model '{self.model}' does not support tool/function calling."
                )

    def _format_messages(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Standardizes messages into OpenAI format, injecting system instruction if present."""
        formatted: List[Dict[str, Any]] = []

        if system_instruction:
            # Check if system message already exists at the beginning
            if not (messages and messages[0].get("role") == "system"):
                formatted.append({"role": "system", "content": system_instruction})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # OpenAI requires 'assistant' instead of Gemini's 'model'
            if role == "model":
                role = "assistant"

            item: Dict[str, Any] = {"role": role, "content": str(content)}
            if "tool_calls" in msg:
                item["tool_calls"] = msg["tool_calls"]
            if "tool_call_id" in msg:
                item["tool_call_id"] = msg["tool_call_id"]
            if "name" in msg:
                item["name"] = msg["name"]
            formatted.append(item)

        return formatted

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Dispatches a chat completion request to the OpenAI-compatible endpoint.
        Normalizes response and tracks token usage accurately.
        """
        self._validate_capabilities(tools=tools)
        url = self._get_chat_url()
        headers = self._build_headers()
        payload_messages = self._format_messages(messages, system_instruction=system_instruction)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "stream": stream,
        }

        # Include tools only when supported and provided
        if tools:
            payload["tools"] = tools

        for key, val in kwargs.items():
            payload[key] = val

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code in [401, 403]:
                    raise AuthenticationError(
                        f"Authentication failed on custom LLM endpoint ({response.status_code}): {response.text}"
                    )
                if response.status_code >= 400:
                    raise ProviderAPIError(
                        f"Custom LLM endpoint returned error {response.status_code}: {response.text}"
                    )

                data = response.json()

        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
            raise EndpointConnectionError(
                f"Failed to connect to custom LLM endpoint at {url}: {net_err}"
            ) from net_err

        return self._normalize_response(data)

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Streams completion tokens as an asynchronous generator.
        """
        url = self._get_chat_url()
        headers = self._build_headers()
        payload_messages = self._format_messages(messages, system_instruction=system_instruction)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "stream": True,
        }
        for key, val in kwargs.items():
            payload[key] = val

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code in [401, 403]:
                        raise AuthenticationError(f"Authentication failed ({resp.status_code})")
                    if resp.status_code >= 400:
                        raise ProviderAPIError(f"Endpoint returned error {resp.status_code}")

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise EndpointConnectionError(f"Streaming connection error: {exc}") from exc

    def _normalize_response(self, data: Dict[str, Any]) -> LLMResponse:
        """
        Normalizes an OpenAI-format JSON response into an internal LLMResponse object.
        Preserves usage metadata if reported; does NOT invent token counts when absent.
        """
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(
                content=None,
                tool_calls=[],
                model=data.get("model", self.model),
                provider=self.provider_name,
                raw_response=data,
            )

        first_choice = choices[0]
        message = first_choice.get("message", {})
        content = message.get("content")
        finish_reason = first_choice.get("finish_reason")

        # Parse tool calls if present
        tool_calls: List[ToolCall] = []
        raw_tool_calls = message.get("tool_calls", [])
        for idx, tc in enumerate(raw_tool_calls):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", f"call_{idx}"),
                    name=fn.get("name", "unknown"),
                    arguments=args if isinstance(args, dict) else {},
                )
            )

        # Parse usage: ONLY if reported by endpoint. DO NOT invent token counts!
        token_usage: Optional[TokenUsage] = None
        raw_usage = data.get("usage")
        if isinstance(raw_usage, dict):
            p_tokens = raw_usage.get("prompt_tokens")
            c_tokens = raw_usage.get("completion_tokens")
            t_tokens = raw_usage.get("total_tokens")
            if p_tokens is not None and c_tokens is not None:
                token_usage = TokenUsage(
                    prompt_tokens=int(p_tokens),
                    completion_tokens=int(c_tokens),
                    total_tokens=int(t_tokens if t_tokens is not None else p_tokens + c_tokens),
                )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=token_usage,
            model=data.get("model", self.model),
            provider=self.provider_name,
            raw_response=data,
        )
