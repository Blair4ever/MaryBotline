from app.tools.base import tool_registry

# Import all tool modules so decorators register them in tool_registry
import app.tools.expenses.expense_tools
import app.tools.reminders.reminder_tools
import app.tools.tasks.task_tools
import app.tools.travel.travel_tools
import app.tools.github.github_tools
import app.agent.tools.memory_tools
import app.agent.tools.summary_tools

__all__ = ["tool_registry"]
