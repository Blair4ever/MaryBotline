from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CapabilityStatus(str, Enum):
    """Status of a model capability."""
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class DeploymentType(str, Enum):
    """Type of deployment for an LLM."""
    CLOUD_API = "cloud_api"
    SELF_HOSTED = "self_hosted"
    GGUF_LOCAL = "gguf_local"
    INFERENCE_PROVIDER = "inference_provider"


class AvailabilityStatus(str, Enum):
    """Availability status of a model."""
    ACTIVE = "active"
    OFFLINE = "offline"
    UNTESTED = "untested"
    DEPRECATED = "deprecated"


class WorkloadType(str, Enum):
    """Workload categories for specialized model routing."""
    GENERAL_CONVERSATION = "general_conversation"
    COMPLEX_REASONING = "complex_reasoning"
    TOOL_EXECUTION = "tool_execution"
    SUMMARIZATION = "summarization"
    LOW_COST_BACKGROUND = "low_cost_background"


class ModelPricing(BaseModel):
    """Pricing information for a model."""
    input_cost_per_million: Optional[float] = None
    output_cost_per_million: Optional[float] = None
    currency: str = "USD"


class TokenUsage(BaseModel):
    """Token consumption reported by the inference endpoint."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ToolCall(BaseModel):
    """Tool/function call request from the model."""
    id: str
    name: str
    arguments: Dict[str, Any]


class LLMResponse(BaseModel):
    """Normalized response from any LLM provider."""
    content: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Optional[TokenUsage] = None  # None when endpoint does not report token counts
    model: Optional[str] = None
    provider: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class ModelCapabilityProfile(BaseModel):
    """
    Capability profile for a specific model.
    Note: Unknown capabilities are marked as unknown and must NEVER be assumed supported.
    """
    model_id: str
    provider: str
    model_family: str
    parameters: Optional[str] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    tool_calling_support: CapabilityStatus = CapabilityStatus.UNKNOWN
    streaming_support: CapabilityStatus = CapabilityStatus.UNKNOWN
    vision_support: CapabilityStatus = CapabilityStatus.UNKNOWN
    reasoning_support: CapabilityStatus = CapabilityStatus.UNKNOWN
    pricing: Optional[ModelPricing] = None
    deployment_type: DeploymentType = DeploymentType.CLOUD_API
    availability_status: AvailabilityStatus = AvailabilityStatus.ACTIVE
    source_repo: Optional[str] = None
    file_name: Optional[str] = None
    quantization: Optional[str] = None
    notes: Optional[str] = None

    def is_tool_calling_supported(self) -> bool:
        """Returns True ONLY if explicitly supported. Unknown returns False."""
        return self.tool_calling_support == CapabilityStatus.SUPPORTED

    def is_streaming_supported(self) -> bool:
        """Returns True ONLY if explicitly supported. Unknown returns False."""
        return self.streaming_support == CapabilityStatus.SUPPORTED

    def is_vision_supported(self) -> bool:
        """Returns True ONLY if explicitly supported. Unknown returns False."""
        return self.vision_support == CapabilityStatus.SUPPORTED

    def is_reasoning_supported(self) -> bool:
        """Returns True ONLY if explicitly supported. Unknown returns False."""
        return self.reasoning_support == CapabilityStatus.SUPPORTED

