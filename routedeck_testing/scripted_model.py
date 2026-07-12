from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr


@dataclass(frozen=True)
class ScriptedModelCall:
    messages: tuple[BaseMessage, ...]
    tool_names: tuple[str, ...]


def tool_call(
    name: str,
    arguments: Mapping[str, Any],
    *,
    call_id: str | None = None,
) -> AIMessage:
    """Create one explicit, deterministic test-only structured tool response."""

    if not name:
        raise ValueError("tool call name must be non-empty")
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": dict(arguments),
                "id": call_id or f"scripted-{name}",
                "type": "tool_call",
            }
        ],
    )


class ScriptedToolModel(BaseChatModel):
    """Fail-loud deterministic model for integration tests only."""

    responses: tuple[AIMessage, ...] = ()
    _cursor: int = PrivateAttr(default=0)
    _bound_tool_names: tuple[str, ...] = PrivateAttr(default=())
    _calls: list[ScriptedModelCall] = PrivateAttr(default_factory=list)

    def __init__(self, responses: Sequence[AIMessage], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.responses = tuple(responses)

    @property
    def calls(self) -> tuple[ScriptedModelCall, ...]:
        return tuple(self._calls)

    @property
    def _llm_type(self) -> str:
        return "routedeck-scripted-tool-model"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ScriptedToolModel:
        del tool_choice, kwargs
        self._bound_tool_names = tuple(_tool_name(tool) for tool in tools)
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        return self._result(messages)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        return self._result(messages)

    def _result(self, messages: list[BaseMessage]) -> ChatResult:
        if self._cursor >= len(self.responses):
            raise AssertionError("ScriptedToolModel response script is exhausted")
        response = self.responses[self._cursor]
        self._cursor += 1
        self._calls.append(
            ScriptedModelCall(
                messages=tuple(messages),
                tool_names=self._bound_tool_names,
            )
        )
        return ChatResult(generations=[ChatGeneration(message=response)])


class ScriptedTextModel(ScriptedToolModel):
    def __init__(self, text: str) -> None:
        super().__init__([AIMessage(content=text)])

    @property
    def _llm_type(self) -> str:
        return "routedeck-scripted-text-model"


def _tool_name(
    tool: dict[str, Any] | type | Callable[..., Any] | BaseTool,
) -> str:
    if isinstance(tool, BaseTool):
        return tool.name
    if not isinstance(tool, Mapping):
        raise TypeError("Scripted model received a tool without a name")
    name = tool.get("name")
    if isinstance(name, str):
        return name
    function = tool.get("function")
    if isinstance(function, Mapping) and isinstance(function.get("name"), str):
        return str(function["name"])
    raise TypeError("Scripted model received a tool without a name")


__all__ = [
    "ScriptedModelCall",
    "ScriptedTextModel",
    "ScriptedToolModel",
    "tool_call",
]
