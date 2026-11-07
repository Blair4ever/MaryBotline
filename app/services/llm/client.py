import abc
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class LLMResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: List[ToolCall] = []
    finish_reason: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMClient(abc.ABC):
    """Abstract interface for LLM providers."""

    @abc.abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
    ) -> LLMResponse:
        pass


class GeminiLLMClient(BaseLLMClient):
    """Client for Google Gemini Models (e.g. Gemini 2.5 Flash)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model or "gemini-2.5-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
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

        return LLMResponse(
            content=response_text if response_text else None,
            tool_calls=tool_calls,
            raw_response=data,
        )


def get_llm_client() -> BaseLLMClient:
    """Factory to retrieve configured LLM client."""
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in ["gemini", "google"]:
        return GeminiLLMClient()
    # Default fallback to Gemini
    return GeminiLLMClient()

