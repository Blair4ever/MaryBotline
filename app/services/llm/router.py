import logging
from typing import Any, Dict, List, Optional, Set, Tuple
import httpx

from app.config import get_settings
from app.services.llm.exceptions import (
    AuthenticationError,
    EndpointConnectionError,
    LLMError,
    ProviderAPIError,
    UnsupportedCapabilityError,
)
from app.services.llm.registry import (
    ModelRegistry,
    QWEN35_DEFIANT_FABLE_GGUF,
    QWEN35_IQ3_M_FILE,
    get_model_registry,
)
from app.services.llm.types import (
    LLMResponse,
    ModelCapabilityProfile,
    WorkloadType,
)

logger = logging.getLogger(__name__)


def normalize_model_name(name: Optional[str]) -> Optional[str]:
    """Resolves short model names (e.g. 'qwen', 'gemini') to canonical model IDs."""
    if not name:
        return None
    lower = name.strip().lower()
    if lower in ["qwen", "qwen3.5", "qwen-3.5", "qwen 3.5", "iq3_m", "qwen-iq3", "uncnr", "defiant"]:
        return QWEN35_IQ3_M_FILE
    if "iq3_m" in lower or "defiant" in lower or "fable" in lower or "uncnr" in lower:
        return QWEN35_IQ3_M_FILE
    if lower in ["gemini", "gemini-flash", "gemini-3.5"]:
        return "gemini-3.5-flash"
    if lower in ["gemini-2.5"]:
        return "gemini-2.5-flash"
    return name


class ModelRouter:
    """
    Intelligent routing and fallback engine for multi-model workloads.
    Validates capability profiles and prevents duplicate tool executions during fallbacks.
    """

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        workload_mappings: Optional[Dict[WorkloadType, str]] = None,
        fallback_model_id: str = "gemini-3.5-flash",
    ) -> None:
        self.registry = registry or get_model_registry()
        self.fallback_model_id = fallback_model_id
        self._workload_mappings: Dict[WorkloadType, str] = workload_mappings or {}
        self._init_default_mappings()

    def _init_default_mappings(self) -> None:
        """Sets up default workload-to-model assignments from configuration."""
        settings = get_settings()

        # If custom LLM is enabled and configured, prefer it for general conversation
        primary_model = (
            settings.custom_llm_model
            if settings.custom_llm_enabled and settings.custom_llm_model
            else settings.llm_model or "gemini-3.5-flash"
        )

        defaults = {
            WorkloadType.GENERAL_CONVERSATION: primary_model,
            WorkloadType.COMPLEX_REASONING: "gemini-3.5-flash",
            # Tool execution requires guaranteed tool-calling capability
            WorkloadType.TOOL_EXECUTION: "gemini-3.5-flash",
            WorkloadType.SUMMARIZATION: "gemini-2.5-flash",
            WorkloadType.LOW_COST_BACKGROUND: "gemini-2.5-flash",
        }
        for workload, model_id in defaults.items():
            if workload not in self._workload_mappings:
                self._workload_mappings[workload] = model_id

    def set_workload_model(self, workload: WorkloadType, model_id: str) -> None:
        """Configures a specific model for a workload category."""
        canonical = normalize_model_name(model_id) or model_id
        self._workload_mappings[workload] = canonical
        logger.info(f"Assigned model '{canonical}' to workload '{workload.value}'.")

    def get_workload_model(self, workload: WorkloadType) -> str:
        """Gets assigned model ID for a workload."""
        return self._workload_mappings.get(workload, self.fallback_model_id)

    def select_model_for_operation(
        self,
        workload: WorkloadType,
        requires_tools: bool = False,
        requires_vision: bool = False,
        group_settings: Optional[Any] = None,
    ) -> Tuple[str, ModelCapabilityProfile]:
        """
        Selects a model verified to support the required capabilities for the operation.
        Enforces rule: A model must not be selected for an operation requiring capabilities it does not support.
        Supports per-group settings overrides.
        """
        target_model_id: Optional[str] = None

        if group_settings:
            if workload == WorkloadType.TOOL_EXECUTION:
                target_model_id = group_settings.tool_execution_model or self.fallback_model_id
            elif workload == WorkloadType.GENERAL_CONVERSATION:
                target_model_id = (
                    group_settings.general_conversation_model
                    or group_settings.default_model
                    or self.get_workload_model(workload)
                )
            elif workload == WorkloadType.COMPLEX_REASONING:
                target_model_id = (
                    group_settings.reasoning_model
                    or group_settings.default_model
                    or self.get_workload_model(workload)
                )
            elif workload == WorkloadType.SUMMARIZATION:
                target_model_id = (
                    group_settings.summarization_model
                    or group_settings.default_model
                    or self.get_workload_model(workload)
                )
            else:
                target_model_id = group_settings.default_model or self.get_workload_model(workload)

        if not target_model_id:
            target_model_id = self.get_workload_model(workload)

        target_model_id = normalize_model_name(target_model_id) or self.fallback_model_id
        profile = self.registry.get(target_model_id)

        # 1. Check if model exists
        if not profile:
            logger.warning(
                f"Model '{target_model_id}' not found in registry. Falling back to '{self.fallback_model_id}'."
            )
            fallback_profile = self.registry.get(self.fallback_model_id)
            if not fallback_profile:
                raise LLMError(f"Fallback model '{self.fallback_model_id}' also not registered.")
            return self.fallback_model_id, fallback_profile

        # 2. Validate tool calling capability if required
        if requires_tools and not profile.is_tool_calling_supported():
            logger.warning(
                f"Model '{target_model_id}' lacks tool-calling support. "
                f"Rerouting to tool-capable fallback model '{self.fallback_model_id}'."
            )
            fallback_profile = self.registry.get(self.fallback_model_id)
            if fallback_profile and fallback_profile.is_tool_calling_supported():
                return self.fallback_model_id, fallback_profile
            raise UnsupportedCapabilityError(
                f"Neither target '{target_model_id}' nor fallback '{self.fallback_model_id}' support tool calling."
            )

        # 3. Validate vision capability if required
        if requires_vision and not profile.is_vision_supported():
            logger.warning(
                f"Model '{target_model_id}' lacks vision support. Rerouting to vision fallback '{self.fallback_model_id}'."
            )
            fallback_profile = self.registry.get(self.fallback_model_id)
            if fallback_profile and fallback_profile.is_vision_supported():
                return self.fallback_model_id, fallback_profile
            raise UnsupportedCapabilityError(
                f"Neither target '{target_model_id}' nor fallback support vision."
            )

        return target_model_id, profile

    async def execute_with_fallback(
        self,
        primary_client: Any,
        fallback_client: Any,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        executed_tool_ids: Optional[Set[str]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Executes chat completion with seamless fallback.
        Preserves complete conversation context and prevents duplicate tool execution.
        """
        executed_ids = executed_tool_ids if executed_tool_ids is not None else set()

        try:
            # Attempt execution on primary client
            response = await primary_client.chat_completion(
                messages=messages,
                tools=tools,
                system_instruction=system_instruction,
                **kwargs,
            )

            # Filter out any tool calls that were already executed
            if response.tool_calls:
                filtered_tool_calls = [tc for tc in response.tool_calls if tc.id not in executed_ids]
                if len(filtered_tool_calls) != len(response.tool_calls):
                    logger.info(
                        f"Filtered out {len(response.tool_calls) - len(filtered_tool_calls)} already executed tool calls."
                    )
                response.tool_calls = filtered_tool_calls

            return response

        except (EndpointConnectionError, ProviderAPIError, AuthenticationError, UnsupportedCapabilityError, LLMError, httpx.HTTPError) as exc:
            logger.warning(
                f"Primary model execution failed ({type(exc).__name__}: {exc}). "
                f"Preserving conversation context and falling back to {fallback_client.__class__.__name__}."
            )

            # Safeguard: Fallback must preserve conversation context intact
            # Copy messages to ensure no corruption of history
            context_messages = [dict(m) for m in messages]

            # Execute on fallback client
            fallback_response = await fallback_client.chat_completion(
                messages=context_messages,
                tools=tools,
                system_instruction=system_instruction,
                **kwargs,
            )

            # Safeguard: Ensure no duplicate tool execution on fallback
            if fallback_response.tool_calls:
                clean_tool_calls = [tc for tc in fallback_response.tool_calls if tc.id not in executed_ids]
                fallback_response.tool_calls = clean_tool_calls

            return fallback_response

