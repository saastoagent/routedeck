from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain_core.messages import AnyMessage, ToolMessage
from langchain_core.tools import BaseTool

from .model_context import (
    RouteDeckModelContext,
    build_model_context,
    merge_reconstructed_messages,
    reconstruct_messages,
)
from .prompt import render_agent_system_message
from .invocation_trace import RouteDeckInvocationTraceRecorder
from .tool_wrapper import (
    RouteDeckInvocationContext,
    RouteDeckRunnerRuntime,
    RouteDeckToolWrapper,
    operation_tool_name,
)


ModelHandler = Callable[
    [ModelRequest[RouteDeckInvocationContext]], Awaitable[ModelResponse[Any]]
]
ToolHandler = Callable[[ToolCallRequest], Awaitable[Any]]


class RouteDeckMiddleware(
    AgentMiddleware[AgentState[Any], RouteDeckInvocationContext, Any]
):
    """LangChain middleware for scoped context and supervised product tools."""

    tools: tuple[BaseTool, ...] = ()

    def __init__(self, runtime: RouteDeckRunnerRuntime, invocation_traces: RouteDeckInvocationTraceRecorder) -> None:
        self.runtime = runtime
        self.tool_wrapper = RouteDeckToolWrapper(runtime)
        self.invocation_traces = invocation_traces

    async def prepare_model_request(
        self,
        request: ModelRequest[RouteDeckInvocationContext],
    ) -> tuple[ModelRequest[RouteDeckInvocationContext], RouteDeckModelContext]:
        """Load current RouteDeck state and derive one safe model request."""

        runtime_context = getattr(request.runtime, "context", None)
        session_id = self.tool_wrapper.session_id(runtime_context)
        snapshot = await self.tool_wrapper.runner.store.load(session_id)
        context = build_model_context(snapshot, self.tool_wrapper.runner.app)
        legal_operation_ids = frozenset(tool.name for tool in context.legal_tools)
        tools = [
            tool
            for tool in request.tools
            if (
                (tool_name := _tool_name(tool)) is not None
                and self.tool_wrapper.operation_id_for_tool_name(tool_name)
                in legal_operation_ids
            )
        ]
        model_context = context.model_copy(
            update={
                "legal_tools": tuple(
                    tool.model_copy(update={"name": operation_tool_name(tool.name)})
                    for tool in context.legal_tools
                )
            }
        )
        messages = cast(
            list[AnyMessage],
            merge_reconstructed_messages(
                reconstruct_messages(
                    snapshot,
                    tool_name_factory=operation_tool_name,
                ),
                request.messages,
            ),
        )
        system_message = render_agent_system_message(
            request.system_message,
            model_context,
        )
        return (
            request.override(
                messages=messages,
                system_message=system_message,
                tools=tools,
            ),
            model_context,
        )

    async def awrap_model_call(
        self,
        request: ModelRequest[RouteDeckInvocationContext],
        handler: ModelHandler,
    ) -> ModelResponse[Any]:
        prepared, model_context = await self.prepare_model_request(request)
        runtime_context = getattr(request.runtime, "context", None)
        session_id = self.tool_wrapper.session_id(runtime_context)
        trace, started = self.invocation_traces.start(session_id, prepared, model_context)
        try:
            response = await handler(prepared)
        except Exception as error:
            self.invocation_traces.fail(trace, started, error)
            raise
        self.invocation_traces.complete(trace, started, response)
        return response

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: ToolHandler,
    ) -> ToolMessage:
        return await self.tool_wrapper.awrap_tool_call(request, handler)


def _tool_name(tool: BaseTool | Mapping[str, Any]) -> str | None:
    if isinstance(tool, BaseTool):
        return tool.name
    name = tool.get("name")
    if isinstance(name, str):
        return name
    function = tool.get("function")
    if isinstance(function, Mapping):
        function_name = function.get("name")
        if isinstance(function_name, str):
            return function_name
    return None


__all__ = ["RouteDeckMiddleware"]
