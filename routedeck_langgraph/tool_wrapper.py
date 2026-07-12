from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, NotRequired, Protocol, TypedDict, runtime_checkable

from langchain.agents.middleware import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.prebuilt import ToolNode

from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationRequest,
    OperationResult,
    OperationSource,
)
from routedeck_core.contracts.conversation import FinalizedConversationTurn
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.state.leases import TurnLease
from routedeck_core.supervision import RouteDeckOperationRunner

from .conversation import extract_conversation_turns, messages_from_agent_state


_EXECUTION_METADATA_KEY = "routedeck_execution"
_EXECUTION_METADATA_VALUE = "runner_only"
_OPERATION_METADATA_KEY = "routedeck_operation_id"
_MAX_TOOL_NAME_LENGTH = 64
_TOOL_NAME_PREFIX = "rd_"
_TOOL_NAME_DIGEST_LENGTH = 12
_TOOL_NAME_READABLE_LENGTH = (
    _MAX_TOOL_NAME_LENGTH - len(_TOOL_NAME_PREFIX) - 1 - _TOOL_NAME_DIGEST_LENGTH
)


class RouteDeckToolConfigurationError(RuntimeError):
    """Raised when a ToolNode is wired to a bypass-capable direct handler."""


class RouteDeckInvocationContext(TypedDict):
    session_id: str
    request_id_prefix: str
    expected_session_version: NotRequired[int]
    turn: NotRequired[TurnLease]
    review_turns: NotRequired[tuple[FinalizedConversationTurn, ...]]
    routedeck_runtime: NotRequired[Any]


@runtime_checkable
class RouteDeckRunnerRuntime(Protocol):
    @property
    def runner(self) -> RouteDeckOperationRunner: ...


ToolContinuation = Callable[[ToolCallRequest], Awaitable[Any]]


class RouteDeckToolWrapper:
    """Execute LangGraph tool calls only through a RouteDeck operation runner.

    LangGraph's ``handler`` callback is a ToolNode continuation, not a second
    product executor. RouteDeck's registered operation binding is the sole
    product handler. Runner-owned tools carry explicit metadata so an arbitrary
    direct ToolNode handler cannot be mistaken for a supervised operation.
    """

    def __init__(
        self,
        runtime: RouteDeckRunnerRuntime | RouteDeckOperationRunner,
    ) -> None:
        self.runner = _runner_from_runtime(runtime)
        self._tools = tuple(
            _runner_owned_tool(operation)
            for operation in self.runner.app.app.operations.values()
        )
        self._operation_ids_by_tool_name: dict[str, str] = {}
        for tool in self._tools:
            operation_id = _declared_operation_id(tool)
            existing = self._operation_ids_by_tool_name.get(tool.name)
            if existing is not None and existing != operation_id:
                raise RouteDeckToolConfigurationError(
                    "RouteDeck operation tool names must be unique"
                )
            self._operation_ids_by_tool_name[tool.name] = operation_id

    @property
    def tools(self) -> tuple[BaseTool, ...]:
        return self._tools

    def operation_id_for_tool_name(self, tool_name: str) -> str:
        """Resolve a provider-facing tool name to its RouteDeck operation ID."""

        if not tool_name:
            raise RouteDeckToolConfigurationError("Tool call name must be non-empty")
        return self._operation_ids_by_tool_name.get(tool_name, tool_name)

    def tool_node(self, tools: Sequence[BaseTool] | None = None) -> ToolNode:
        """Create a raw ToolNode wrapper without receiving or mutating a graph."""

        selected = tuple(tools) if tools is not None else self.tools
        for tool in selected:
            _require_runner_owned_tool(tool)
        return ToolNode(selected, awrap_tool_call=self.awrap_tool_call)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: ToolContinuation,
    ) -> ToolMessage:
        """Supervise one structured call and return its typed tool observation.

        ``handler`` is deliberately not called: doing so would execute the
        schema tool after the registered RouteDeck product binding and create a
        double-execution path. Its presence is validated as the LangGraph
        continuation contract, and known tools must carry runner-only identity
        metadata. Unknown tool names still enter the runner and receive its
        canonical ``operation_not_available`` result.
        """

        if not callable(handler):
            raise RouteDeckToolConfigurationError(
                "LangGraph tool continuation must be callable"
            )
        tool_call = request.tool_call
        tool_name = tool_call.get("name")
        call_id = tool_call.get("id")
        arguments = tool_call.get("args", {})
        if not isinstance(tool_name, str) or not tool_name:
            raise RouteDeckToolConfigurationError("Tool call name must be non-empty")
        operation_id = self.operation_id_for_tool_name(tool_name)
        if not isinstance(call_id, str) or not call_id:
            raise RouteDeckToolConfigurationError("Tool call ID must be non-empty")
        if not isinstance(arguments, Mapping):
            raise RouteDeckToolConfigurationError(
                "RouteDeck tool arguments must be a JSON object"
            )
        if request.tool is not None:
            _require_runner_owned_tool(
                request.tool,
                operation_id=operation_id,
                tool_name=tool_name,
            )

        context = getattr(request.runtime, "context", None)
        session_id = self.session_id(context)
        snapshot = await self.runner.store.load(session_id)
        supplied_version = _context_value(context, "expected_session_version")
        expected_version = (
            supplied_version
            if isinstance(supplied_version, int)
            else snapshot.session_version
        )
        prefix = _context_value(context, "request_id_prefix")
        if not isinstance(prefix, str) or not prefix:
            raise RouteDeckToolConfigurationError(
                "request_id_prefix must be a non-empty string"
            )
        turn = _context_value(context, "turn")
        if turn is not None and not isinstance(turn, TurnLease):
            raise RouteDeckToolConfigurationError("turn must be a TurnLease")
        review_turns = _context_value(context, "review_turns")
        if review_turns is None:
            review_turns = ()
        if not isinstance(review_turns, (list, tuple)) or any(
            not isinstance(item, FinalizedConversationTurn) for item in review_turns
        ):
            raise RouteDeckToolConfigurationError(
                "review_turns must contain finalized conversation turns"
            )
        review_tool_call = None
        if review_turns:
            if len(review_turns) != 1:
                raise RouteDeckToolConfigurationError(
                    "review_turns must contain exactly the current user marker"
                )
            extracted = extract_conversation_turns(
                messages_from_agent_state(request.state),
                current_user_turn=review_turns[0],
                id_factory=self.runner.id_factory,
                pending_tool_call_id=call_id,
            )
            review_turns = extracted.turns
            review_tool_call = extracted.pending_tool_call
            if review_tool_call is not None:
                review_tool_call = review_tool_call.model_copy(
                    update={"name": operation_id}
                )

        result = await self.runner.run(
            OperationRequest(
                session_id=session_id,
                request_id=f"{prefix}:{call_id}",
                expected_session_version=expected_version,
                operation_id=operation_id,
                source=OperationSource.AGENT,
                arguments=FrozenJsonObject(dict(arguments)),
            ),
            turn=turn,
            review_turns=tuple(review_turns),
            review_tool_call=review_tool_call,
        )
        return _tool_message(result, tool_call_id=call_id, tool_name=tool_name)

    def session_id(self, context: object | None) -> str:
        session_id = _context_value(context, "session_id")
        if not isinstance(session_id, str) or not session_id:
            raise RouteDeckToolConfigurationError(
                "session_id must be a non-empty string"
            )
        return session_id


async def awrap_tool_call(
    request: ToolCallRequest,
    handler: ToolContinuation,
) -> ToolMessage:
    """Raw ToolNode callback that resolves RouteDeck runtime from graph context."""

    context = getattr(request.runtime, "context", None)
    runtime = _context_value(context, "routedeck_runtime")
    if runtime is None:
        raise RouteDeckToolConfigurationError(
            "Raw awrap_tool_call requires context['routedeck_runtime']"
        )
    return await RouteDeckToolWrapper(runtime).awrap_tool_call(request, handler)


def _runner_from_runtime(
    runtime: RouteDeckRunnerRuntime | RouteDeckOperationRunner,
) -> RouteDeckOperationRunner:
    if isinstance(runtime, RouteDeckOperationRunner):
        return runtime
    runner = getattr(runtime, "runner", None)
    if not isinstance(runner, RouteDeckOperationRunner):
        raise RouteDeckToolConfigurationError(
            "RouteDeck LangGraph runtime must expose a RouteDeckOperationRunner"
        )
    return runner


def _runner_owned_tool(operation: Any) -> StructuredTool:
    async def _must_run_through_wrapper(**_: Any) -> Any:
        raise RouteDeckToolConfigurationError(
            f"Tool {operation.id!r} must execute through RouteDeckToolWrapper"
        )

    return StructuredTool.from_function(
        coroutine=_must_run_through_wrapper,
        name=operation_tool_name(operation.id),
        description=operation.description or operation.title,
        args_schema=operation.input_schema_value(),
        infer_schema=False,
        metadata={
            _EXECUTION_METADATA_KEY: _EXECUTION_METADATA_VALUE,
            _OPERATION_METADATA_KEY: operation.id,
        },
    )


def _require_runner_owned_tool(
    tool: BaseTool,
    *,
    operation_id: str | None = None,
    tool_name: str | None = None,
) -> None:
    declared_id = _declared_operation_id(tool)
    expected_id = operation_id or declared_id
    expected_name = tool_name or operation_tool_name(expected_id)
    if declared_id != expected_id or tool.name != expected_name:
        raise RouteDeckToolConfigurationError(
            f"Tool {tool.name!r} is not a runner-owned RouteDeck schema tool; "
            "direct ToolNode handlers are unsupported"
        )


def _declared_operation_id(tool: BaseTool) -> str:
    metadata = tool.metadata or {}
    declared_id = metadata.get(_OPERATION_METADATA_KEY)
    if (
        metadata.get(_EXECUTION_METADATA_KEY) != _EXECUTION_METADATA_VALUE
        or not isinstance(declared_id, str)
        or not declared_id
    ):
        raise RouteDeckToolConfigurationError(
            f"Tool {tool.name!r} is not a runner-owned RouteDeck schema tool; "
            "direct ToolNode handlers are unsupported"
        )
    return declared_id


def operation_tool_name(operation_id: str) -> str:
    """Return a stable provider-safe name for one RouteDeck operation ID."""

    if not operation_id:
        raise ValueError("RouteDeck operation ID must be non-empty")
    readable = "".join(
        character
        if character.isascii() and (character.isalnum() or character in {"_", "-"})
        else "_"
        for character in operation_id
    ).strip("_-")
    if not readable:
        readable = "operation"
    digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[
        :_TOOL_NAME_DIGEST_LENGTH
    ]
    return f"{_TOOL_NAME_PREFIX}{readable[:_TOOL_NAME_READABLE_LENGTH]}_{digest}"


def _context_value(context: object | None, key: str) -> Any:
    if isinstance(context, Mapping):
        return context.get(key)
    return getattr(context, key, None)


def _tool_message(
    result: OperationResult,
    *,
    tool_call_id: str,
    tool_name: str,
) -> ToolMessage:
    payload: dict[str, Any] = {
        "type": "routedeck_operation_result",
        "disposition": result.disposition.value,
        "operation_id": result.operation_id,
        "session_version": result.session_version,
        "projection_version": result.projection_version,
    }
    if result.outcome is not None:
        payload["outcome"] = result.outcome
    if result.review is not None:
        payload["review"] = {
            "id": result.review.id,
            "expires_at": result.review.expires_at.isoformat(),
        }
    if result.failure is not None:
        payload["failure"] = {
            "code": result.failure.code,
            "message": result.failure.public_message,
            "recovery_directive": result.failure.recovery_directive,
        }
    error_dispositions = {
        OperationDisposition.BLOCKED,
        OperationDisposition.NEEDS_INPUT,
        OperationDisposition.FAILED,
        OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN,
    }
    return ToolMessage(
        content=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        artifact=payload,
        name=tool_name,
        status="error" if result.disposition in error_dispositions else "success",
        tool_call_id=tool_call_id,
    )


__all__ = [
    "RouteDeckInvocationContext",
    "RouteDeckRunnerRuntime",
    "RouteDeckToolConfigurationError",
    "RouteDeckToolWrapper",
    "awrap_tool_call",
    "operation_tool_name",
]
