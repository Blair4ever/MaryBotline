from enum import Enum


class AutonomyLevel(str, Enum):
    """
    Three-tier autonomy levels:
    - L1 (Observe): Silent observation and context/factual memory extraction.
    - L2 (Assist): Proactive drafts, suggestions, clarifications, and summaries.
    - L3 (Execute): Execution of registered tools and external operations.
    """
    L1_OBSERVE = "L1"
    L2_ASSIST = "L2"
    L3_EXECUTE = "L3"


class ActionPolicy(str, Enum):
    """Execution policy for autonomous actions."""
    AUTOMATIC = "automatic"
    CONFIRM_AMBIGUOUS = "confirm_ambiguous"
    REQUIRE_APPROVAL = "require_approval"
    EXPLICIT_CONFIRMATION = "explicit_confirmation"

