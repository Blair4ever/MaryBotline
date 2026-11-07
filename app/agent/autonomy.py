from enum import Enum


class AutonomyLevel(str, Enum):
    """
    Autonomy levels defined in the MARY architecture:
    - L1 (Observe): Analyze incoming messages, extract context and factual group memory.
    - L2 (Assist): Propose solutions, prepare drafts, estimate expenses, ask clarifying questions.
    - L3 (Execute): Execute authorized actions using registered tools.
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

