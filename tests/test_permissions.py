import pytest
from app.permissions.policies import ActionPolicy
from app.permissions.engine import PermissionEngine


def test_permission_engine_automatic_actions():
    assert PermissionEngine.get_action_policy("summarize_messages") == ActionPolicy.AUTOMATIC
    assert PermissionEngine.get_action_policy("answer_question") == ActionPolicy.AUTOMATIC
    assert PermissionEngine.can_auto_execute("summarize_messages") is True


def test_permission_engine_destructive_actions():
    assert PermissionEngine.get_action_policy("delete_repository") == ActionPolicy.EXPLICIT_CONFIRMATION
    assert PermissionEngine.can_auto_execute("delete_repository") is False

    assert PermissionEngine.get_action_policy("transfer_money") == ActionPolicy.REQUIRE_APPROVAL
    assert PermissionEngine.can_auto_execute("transfer_money") is False


def test_permission_engine_conditional_actions():
    # Ambiguous expense requires confirmation
    assert PermissionEngine.can_auto_execute("record_expense", has_ambiguity=True) is False
    # Clear expense can proceed
    assert PermissionEngine.can_auto_execute("record_expense", has_ambiguity=False) is True

