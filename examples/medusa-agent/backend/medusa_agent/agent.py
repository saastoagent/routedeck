from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from routedeck_langgraph import (
    RouteDeckInvocationContext,
    RouteDeckMiddleware,
    RouteDeckRunnerRuntime,
    RouteDeckToolWrapper,
)

from .turn_policy import MedusaTurnPolicyMiddleware, ModelTurnPolicy, TurnPolicy

if TYPE_CHECKING:
    from .config import Settings


BUYER_AGENT_PROMPT = """\
You are the Medusa buyer assistant for one guest shopping session.

Help the buyer shop in a concise, friendly, and practical voice. Use the
RouteDeck capabilities and current context supplied to you at runtime.

At a fresh buyer.home session, the product may invoke you before the buyer
sends a message. In that invocation, begin the conversation with a concise,
friendly greeting that starts with "Hi". Do not call a tool, claim a state
change, or imply that the buyer sent a message.
"""


class MissingModelCredential(RuntimeError):
    """Raised when live agent construction lacks explicit OpenAI credentials."""


def create_medusa_agent(
    *,
    model: BaseChatModel,
    runtime: RouteDeckRunnerRuntime,
    turn_policy: TurnPolicy,
) -> Any:
    """Create a request-scoped Medusa agent with an injected model and runtime."""

    wrapper = RouteDeckToolWrapper(runtime)
    middleware = RouteDeckMiddleware(runtime)
    turn_policy_middleware = MedusaTurnPolicyMiddleware(turn_policy)
    agent = create_agent(
        model=model,
        tools=wrapper.tools,
        middleware=(middleware, turn_policy_middleware),
        system_prompt=BUYER_AGENT_PROMPT,
        context_schema=RouteDeckInvocationContext,
        name="medusa_buyer_agent",
    )
    # Public composition evidence for contract tests and developer inspection.
    # These attributes do not participate in execution; create_agent owns the
    # unchanged LangGraph topology and the middleware owns the RouteDeck seam.
    agent.middleware_types = (  # type: ignore[attr-defined]
        RouteDeckMiddleware,
        MedusaTurnPolicyMiddleware,
    )
    agent.route_deck_middleware = middleware  # type: ignore[attr-defined]
    agent.turn_policy_middleware = turn_policy_middleware  # type: ignore[attr-defined]
    return agent


def create_medusa_entry_agent(*, model: BaseChatModel) -> Any:
    """Create the no-tool agent used to begin a buyer.home conversation."""

    return create_agent(
        model=model,
        tools=(),
        system_prompt=BUYER_AGENT_PROMPT,
        name="medusa_buyer_entry_agent",
    )


def create_live_medusa_agent(
    *,
    settings: Settings,
    runtime: RouteDeckRunnerRuntime,
) -> Any:
    """Create the live OpenAI-backed buyer agent without a fallback model."""

    return create_medusa_agent(
        model=_create_live_tool_model(settings=settings),
        runtime=runtime,
        turn_policy=ModelTurnPolicy(_create_live_turn_policy_model(settings=settings)),
    )


def create_live_medusa_entry_agent(*, settings: Settings) -> Any:
    """Create the live no-tool agent that begins a buyer.home conversation."""

    return create_medusa_entry_agent(
        model=_create_live_entry_model(settings=settings)
    )


def _create_live_tool_model(*, settings: Settings) -> BaseChatModel:
    """Construct the configured model for the tool-enabled buyer agent."""

    _require_live_model_settings(settings)
    return ChatOpenAI(
        model=settings.openai_buyer_model,
        api_key=settings.openai_api_key,
        streaming=True,
    )


def _create_live_entry_model(*, settings: Settings) -> BaseChatModel:
    """Construct the configured model for the no-tool buyer entry agent."""

    _require_live_model_settings(settings)
    return ChatOpenAI(
        model=settings.openai_entry_model,
        api_key=settings.openai_api_key,
        streaming=True,
    )


def _create_live_turn_policy_model(*, settings: Settings) -> BaseChatModel:
    """Construct the no-tool structured model that classifies buyer turns."""

    _require_live_model_settings(settings)
    return ChatOpenAI(
        model=settings.openai_turn_policy_model,
        api_key=settings.openai_api_key,
    )


def _require_live_model_settings(settings: Settings) -> None:
    """Validate the explicit live-model credential contract."""

    if settings.openai_api_key is None:
        raise MissingModelCredential(
            "OPENAI_API_KEY is required for the live Medusa buyer agent"
        )
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        raise MissingModelCredential(
            "OPENAI_API_KEY is required for the live Medusa buyer agent"
        )


__all__ = [
    "BUYER_AGENT_PROMPT",
    "MissingModelCredential",
    "create_medusa_entry_agent",
    "create_live_medusa_entry_agent",
    "create_live_medusa_agent",
    "create_medusa_agent",
]
