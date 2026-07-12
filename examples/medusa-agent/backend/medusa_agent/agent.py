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

if TYPE_CHECKING:
    from .config import Settings


BUYER_AGENT_PROMPT = """\
You are the Medusa buyer assistant for one guest shopping session.

Use only the tools listed in the current RouteDeck context. Tool arguments must
use the opaque interaction handles in that context exactly as supplied. Call
tools serially: wait for each tool result before deciding whether to call the
next tool. Treat completed tool results and the refreshed RouteDeck context as
the only authority for commerce state.

Never claim that cart, checkout, payment, review, order, navigation, or product
selection state changed unless a completed tool result confirms it. Never infer
private Store identifiers or ask for private checkout fields in chat. When a
tool reports that review or buyer input is required, explain that state without
pretending the protected action completed.
"""


class MissingModelCredential(RuntimeError):
    """Raised when live agent construction lacks explicit OpenAI credentials."""


def create_medusa_agent(
    *,
    model: BaseChatModel,
    runtime: RouteDeckRunnerRuntime,
) -> Any:
    """Create a request-scoped Medusa agent with an injected model and runtime."""

    wrapper = RouteDeckToolWrapper(runtime)
    middleware = RouteDeckMiddleware(runtime)
    agent = create_agent(
        model=model,
        tools=wrapper.tools,
        middleware=(middleware,),
        system_prompt=BUYER_AGENT_PROMPT,
        context_schema=RouteDeckInvocationContext,
        name="medusa_buyer_agent",
    )
    # Public composition evidence for contract tests and developer inspection.
    # These attributes do not participate in execution; create_agent owns the
    # unchanged LangGraph topology and the middleware owns the RouteDeck seam.
    agent.middleware_types = (RouteDeckMiddleware,)  # type: ignore[attr-defined]
    agent.route_deck_middleware = middleware  # type: ignore[attr-defined]
    return agent


def create_live_medusa_agent(
    *,
    settings: Settings,
    runtime: RouteDeckRunnerRuntime,
) -> Any:
    """Create the live OpenAI-backed buyer agent without a fallback model."""

    if settings.openai_api_key is None:
        raise MissingModelCredential(
            "OPENAI_API_KEY is required for the live Medusa buyer agent"
        )
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        raise MissingModelCredential(
            "OPENAI_API_KEY is required for the live Medusa buyer agent"
        )
    if not settings.openai_model:
        raise MissingModelCredential(
            "OPENAI_MODEL is required for the live Medusa buyer agent"
        )
    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        streaming=True,
        model_kwargs={"parallel_tool_calls": False},
    )
    return create_medusa_agent(model=model, runtime=runtime)


__all__ = [
    "BUYER_AGENT_PROMPT",
    "MissingModelCredential",
    "create_live_medusa_agent",
    "create_medusa_agent",
]
