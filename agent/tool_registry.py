"""Schema-validated tool registry for FreshSense agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from agent.contracts import ToolExecution


class AgentToolError(RuntimeError):
    """Raised when an agent requests an unavailable or invalid tool call."""


@dataclass(frozen=True)
class AgentToolContext:
    identity_hash: str
    inspection_id: str
    store: Any


ToolHandler = Callable[[BaseModel, AgentToolContext], dict[str, Any]]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler

    def openai_schema(self) -> dict[str, Any]:
        """Return the function schema used by a future structured LLM planner."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.input_model.model_json_schema(),
            "strict": True,
        }


class AgentToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        if not tool.name or tool.name in self._tools:
            raise AgentToolError(f"Agent tool {tool.name!r} is invalid or duplicated.")
        self._tools[tool.name] = tool

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: AgentToolContext,
    ) -> ToolExecution:
        tool = self._tools.get(tool_name)
        if tool is None:
            raise AgentToolError(f"Agent tool {tool_name!r} is not registered.")
        try:
            parsed = tool.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise AgentToolError(
                f"Agent tool {tool_name!r} received invalid arguments."
            ) from exc
        output = tool.handler(parsed, context)
        if not isinstance(output, dict):
            raise AgentToolError(f"Agent tool {tool_name!r} returned an invalid result.")
        return ToolExecution(tool_name=tool_name, output=output)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.openai_schema() for tool in self._tools.values()]


__all__ = [
    "AgentTool",
    "AgentToolContext",
    "AgentToolError",
    "AgentToolRegistry",
]
