import inspect
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    fn: Optional[Callable] = None


class ToolRegistry:
    """Central registry for all AI-executable tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, parameters: Dict[str, Any]) -> Callable:
        """Decorator to register a python function as an agent tool."""
        def decorator(func: Callable) -> Callable:
            tool_def = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                fn=func,
            )
            self._tools[name] = tool_def
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def get_openai_tools_schema(self) -> List[Dict[str, Any]]:
        """Export tools in standard OpenAI / Gemini tool call format."""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas


# Global registry singleton
tool_registry = ToolRegistry()

