from typing import Any, Dict
from app.permissions.policies import ActionPolicy, AutonomyLevel


class PermissionEngine:
    """
    Enforces security boundaries, action policies, and human-in-the-loop approval workflows.
    Prevents the LLM from executing destructive or unverified operations.
    """

    POLICY_MAP: Dict[str, ActionPolicy] = {
        "summarize_messages": ActionPolicy.AUTOMATIC,
        "answer_question": ActionPolicy.AUTOMATIC,
        "extract_tasks": ActionPolicy.AUTOMATIC,
        "create_reminder": ActionPolicy.AUTOMATIC,
        "calculate_expenses": ActionPolicy.AUTOMATIC,
        "record_expense": ActionPolicy.CONFIRM_AMBIGUOUS,
        "plan_trip": ActionPolicy.AUTOMATIC,
        "book_hotel": ActionPolicy.REQUIRE_APPROVAL,
        "transfer_money": ActionPolicy.REQUIRE_APPROVAL,
        "create_github_draft": ActionPolicy.AUTOMATIC,
        "publish_public_repo": ActionPolicy.REQUIRE_APPROVAL,
        "delete_repository": ActionPolicy.EXPLICIT_CONFIRMATION,
    }

    @classmethod
    def get_action_policy(cls, tool_name: str) -> ActionPolicy:
        """Returns the security policy required for a given tool/action."""
        return cls.POLICY_MAP.get(tool_name, ActionPolicy.REQUIRE_APPROVAL)

    @classmethod
    def can_auto_execute(cls, tool_name: str, has_ambiguity: bool = False) -> bool:
        """Checks if the tool can be safely executed autonomously without user approval."""
        policy = cls.get_action_policy(tool_name)
        if policy == ActionPolicy.AUTOMATIC:
            return True
        if policy == ActionPolicy.CONFIRM_AMBIGUOUS and not has_ambiguity:
            return True
        return False

