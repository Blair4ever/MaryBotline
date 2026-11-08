import logging
from typing import Dict, List, Optional

from app.services.llm.types import (
    AvailabilityStatus,
    CapabilityStatus,
    DeploymentType,
    ModelCapabilityProfile,
    ModelPricing,
)

logger = logging.getLogger(__name__)


# Specific Qwen3.5 fine-tuned model identifiers
QWEN35_DEFIANT_FABLE_GGUF = "Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF"
QWEN35_IQ3_M_FILE = "Qwen3.5-9B-The-Defiant-Fable-Uncnr-Heretic-NEO-MAX-MTP-IQ3_M.gguf"
QWEN35_REPO_URL = "https://huggingface.co/CapitalSTEEZ47/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF"


class ModelRegistry:
    """
    Central registry that separates provider configuration from model configuration.
    Stores and validates capability profiles for all supported models.
    """

    def __init__(self) -> None:
        self._models: Dict[str, ModelCapabilityProfile] = {}
        self._init_default_models()

    def _init_default_models(self) -> None:
        """Register built-in models and fine-tuned/open-weight model profiles."""
        # 1. Google Gemini 2.5 Flash
        self.register(
            ModelCapabilityProfile(
                model_id="gemini-2.5-flash",
                provider="google",
                model_family="Gemini",
                parameters="Unknown",
                context_window=1048576,
                max_output_tokens=8192,
                tool_calling_support=CapabilityStatus.SUPPORTED,
                streaming_support=CapabilityStatus.SUPPORTED,
                vision_support=CapabilityStatus.SUPPORTED,
                reasoning_support=CapabilityStatus.SUPPORTED,
                pricing=ModelPricing(input_cost_per_million=0.075, output_cost_per_million=0.30),
                deployment_type=DeploymentType.CLOUD_API,
                availability_status=AvailabilityStatus.ACTIVE,
                notes="Google official multimodal Flash model",
            )
        )

        # 2. Google Gemini 3.5 Flash
        self.register(
            ModelCapabilityProfile(
                model_id="gemini-3.5-flash",
                provider="google",
                model_family="Gemini",
                parameters="Unknown",
                context_window=1048576,
                max_output_tokens=8192,
                tool_calling_support=CapabilityStatus.SUPPORTED,
                streaming_support=CapabilityStatus.SUPPORTED,
                vision_support=CapabilityStatus.SUPPORTED,
                reasoning_support=CapabilityStatus.SUPPORTED,
                pricing=ModelPricing(input_cost_per_million=0.075, output_cost_per_million=0.30),
                deployment_type=DeploymentType.CLOUD_API,
                availability_status=AvailabilityStatus.ACTIVE,
                notes="Active default Gemini reasoning model",
            )
        )

        # 3. Fine-tuned Qwen3.5 9B GGUF Model (Repository Level)
        self.register(
            ModelCapabilityProfile(
                model_id=QWEN35_DEFIANT_FABLE_GGUF,
                provider="custom",
                model_family="Qwen3.5",
                parameters="9B",
                context_window=32768,
                max_output_tokens=8192,
                tool_calling_support=CapabilityStatus.UNSUPPORTED,
                streaming_support=CapabilityStatus.SUPPORTED,
                vision_support=CapabilityStatus.UNSUPPORTED,
                reasoning_support=CapabilityStatus.SUPPORTED,
                pricing=None,  # Open-weight / self-hosted
                deployment_type=DeploymentType.GGUF_LOCAL,
                availability_status=AvailabilityStatus.ACTIVE,
                source_repo=QWEN35_REPO_URL,
                file_name=QWEN35_IQ3_M_FILE,
                quantization="IQ3_M",
                notes="Fine-tuned Qwen3.5 9B in GGUF format (CapitalSTEEZ47) with IQ3_M quantization.",
            )
        )

        # 4. Fine-tuned Qwen3.5 9B Specific GGUF File Variant (IQ3_M)
        self.register(
            ModelCapabilityProfile(
                model_id=QWEN35_IQ3_M_FILE,
                provider="custom",
                model_family="Qwen3.5",
                parameters="9B",
                context_window=32768,
                max_output_tokens=8192,
                tool_calling_support=CapabilityStatus.UNSUPPORTED,
                streaming_support=CapabilityStatus.SUPPORTED,
                vision_support=CapabilityStatus.UNSUPPORTED,
                reasoning_support=CapabilityStatus.SUPPORTED,
                pricing=None,  # Open-weight / self-hosted
                deployment_type=DeploymentType.GGUF_LOCAL,
                availability_status=AvailabilityStatus.ACTIVE,
                source_repo=QWEN35_REPO_URL,
                file_name=QWEN35_IQ3_M_FILE,
                quantization="IQ3_M",
                notes="Fine-tuned Qwen3.5 9B GGUF IQ3_M quantization file from CapitalSTEEZ47.",
            )
        )

    def register(self, profile: ModelCapabilityProfile) -> None:
        """Register or update a model capability profile."""
        self._models[profile.model_id] = profile
        logger.debug(f"Registered model capability profile: {profile.model_id} ({profile.model_family})")

    def get(self, model_id: str) -> Optional[ModelCapabilityProfile]:
        """Retrieve a model capability profile by model ID."""
        return self._models.get(model_id)

    def list_models(self) -> List[ModelCapabilityProfile]:
        """List all registered models."""
        return list(self._models.values())

    def validate_capability(self, model_id: str, capability: str) -> bool:
        """
        Validates if a model explicitly supports a capability.
        Unknown or missing capabilities return False.
        """
        profile = self.get(model_id)
        if not profile:
            logger.warning(f"Model '{model_id}' not found in registry. Capability '{capability}' treated as unsupported.")
            return False

        attr_name = f"{capability}_support"
        if not hasattr(profile, attr_name):
            logger.warning(f"Capability '{capability}' not recognized in profile.")
            return False

        status = getattr(profile, attr_name)
        # MUST be explicitly SUPPORTED. Unknown is treated as unsupported.
        return status == CapabilityStatus.SUPPORTED


_global_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Singleton getter for the ModelRegistry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ModelRegistry()
    return _global_registry

