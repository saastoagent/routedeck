from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from enum import StrEnum
from typing import Any, Protocol

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ConfigDict

from routedeck_langgraph import RouteDeckInvocationContext


TURN_POLICY_PROMPT = """\
Classify the current buyer turn for the Medusa commerce agent.

Choose action only when fulfilling the current user turn requires reading or
changing commerce application state, selecting an application destination, or
invoking another declared commerce operation. Choose conversation when the
turn can be answered without an application operation. Prior application
activity alone is not permission to perform another operation. Resolve social,
informational, or otherwise non-operational turns as conversation.

This classification controls whether commerce tools are available. It does not
select a tool or decide whether an operation is legal; RouteDeck owns operation
legality and supervision.
"""

TURN_POLICY_EVENT_TAG = "medusa.turn_policy"

CONVERSATION_MODE_PROMPT = """\
The current turn is conversational. Respond directly without performing or
claiming any commerce operation, navigation, or application-state change.
"""


class TurnMode(StrEnum):
    CONVERSATION = "conversation"
    ACTION = "action"


class TurnDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TurnMode


class TurnPolicy(Protocol):
    async def decide(self, messages: Sequence[BaseMessage]) -> TurnMode | str: ...


class ModelTurnPolicy:
    """Use a no-tool structured model call to classify one buyer turn."""

    def __init__(self, model: BaseChatModel) -> None:
        self._classifier = model.with_structured_output(
            TurnDecision,
            method="json_schema",
            strict=True,
        )

    async def decide(self, messages: Sequence[BaseMessage]) -> TurnMode:
        decision = await self._classifier.ainvoke(
            [SystemMessage(content=TURN_POLICY_PROMPT), *messages],
            config={
                "run_name": "medusa_turn_policy",
                "tags": [TURN_POLICY_EVENT_TAG],
            },
        )
        if not isinstance(decision, TurnDecision):
            raise TypeError("The Medusa turn policy returned an invalid decision")
        return decision.mode


class MedusaTurnPolicyMiddleware(AgentMiddleware):
    """Expose commerce tools only for turns classified as application actions."""

    def __init__(self, policy: TurnPolicy) -> None:
        self._policy = policy

    async def awrap_model_call(
        self,
        request: ModelRequest[RouteDeckInvocationContext],
        handler: Callable[
            [ModelRequest[RouteDeckInvocationContext]],
            Awaitable[ModelResponse[Any]],
        ],
    ) -> ModelResponse[Any]:
        if _current_turn_has_tool_result(request.messages):
            return await handler(request)

        mode = TurnMode(await self._policy.decide(request.messages))
        if mode is TurnMode.ACTION:
            return await handler(request)

        return await handler(
            request.override(
                tools=[],
                system_message=_append_system_message(
                    request.system_message,
                    CONVERSATION_MODE_PROMPT,
                ),
            )
        )


def _current_turn_has_tool_result(messages: Sequence[BaseMessage]) -> bool:
    current_user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], HumanMessage)
        ),
        None,
    )
    if current_user_index is None:
        return False
    return any(
        isinstance(message, ToolMessage)
        for message in messages[current_user_index + 1 :]
    )


def _append_system_message(
    current: SystemMessage | None,
    addition: str,
) -> SystemMessage:
    if current is None:
        return SystemMessage(content=addition)
    return SystemMessage(content=f"{current.text}\n\n{addition}")


__all__ = [
    "MedusaTurnPolicyMiddleware",
    "ModelTurnPolicy",
    "TURN_POLICY_EVENT_TAG",
    "TurnDecision",
    "TurnMode",
    "TurnPolicy",
]
