from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import Settings
from core.protocol import (
    agent_end,
    agent_start,
    chunk_text,
    error,
    message_delta,
    stream_end,
    stream_start,
)
from services.graph_builder import COMMERCE_SYSTEM_PROMPT
from services.agent_tools import projection_update_from_tool_output
from services.planning_context import build_planning_context, planning_context_message
from services.route_events import route_event_bus
from services.routedeck_projection import build_runtime_medusa_projection


logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, settings: Settings | None = None, graph: Any | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.graph = graph
        self._debug_threads: dict[str, dict[str, Any]] = {}
        self._latest_conversation_id: str | None = None

    def debug_context_thread(self, conversation_id: str | None = None) -> dict[str, Any]:
        selected_conversation_id = conversation_id or self._latest_conversation_id
        if not selected_conversation_id:
            return _empty_debug_context(self.settings.medusa_agent_model)

        return self._debug_threads.get(
            selected_conversation_id,
            {
                **_empty_debug_context(self.settings.medusa_agent_model),
                "conversation_id": selected_conversation_id,
            },
        )

    async def stream(
        self,
        message: str,
        conversation_id: str | None = None,
        route_context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        conversation_id = conversation_id or f"conv-{uuid.uuid4().hex}"

        yield stream_start(
            conversation_id=conversation_id,
            model=self.settings.medusa_agent_model,
        )
        yield agent_start()

        try:
            if not message.strip():
                yield error("Please send a shopping question or product request.", "empty_message")
            elif not self.settings.openai_api_key:
                yield error(
                    "OPENAI_API_KEY is required for the Medusa agent.",
                    "openai_api_key_missing",
                )
            else:
                async for item in self._stream_graph(
                    message,
                    conversation_id,
                    route_context,
                ):
                    if item["event"] == "message_delta":
                        yield message_delta(item["content"])
        except TimeoutError:
            yield error("The shopping assistant took too long to respond. Please try again.", "timeout")
        except Exception as exc:
            logger.exception(
                "medusa_agent_stream_failed",
                extra={
                    "conversation_id": conversation_id,
                    "model": self.settings.medusa_agent_model,
                    "error_type": type(exc).__name__,
                },
            )
            yield error("The shopping assistant could not answer that just now.", "agent_error")

        yield agent_end()
        yield stream_end()

    async def _stream_graph(
        self,
        message: str,
        conversation_id: str,
        route_context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        graph = self.graph
        if graph is None:
            from services import graph_builder

            graph = graph_builder.build_agent_graph(self.settings)
            self.graph = graph

        config = {"configurable": {"thread_id": conversation_id}}
        messages = _agent_messages(message, route_context, self.settings)
        self._record_debug_turn_start(
            conversation_id,
            messages,
            route_context,
        )
        assistant_chunks: list[str] = []

        async def iterate() -> AsyncGenerator[dict[str, Any], None]:
            async for event in graph.astream_events(
                {"messages": messages},
                config=config,
                version="v2",
            ):
                event_name = event.get("event")
                if event_name == "on_tool_end":
                    next_projection_update = projection_update_from_tool_output(
                        event.get("data", {}).get("output"),
                        route_context,
                    )
                    if next_projection_update:
                        self._record_debug_projection_update(conversation_id, next_projection_update)
                        route_event_bus.publish(conversation_id, next_projection_update)
                    continue

                if event_name != "on_chat_model_stream":
                    continue
                chunk = event.get("data", {}).get("chunk")
                content = chunk_text(getattr(chunk, "content", ""))
                if content:
                    assistant_chunks.append(content)
                    yield {"event": "message_delta", "content": content}

        async with asyncio.timeout(self.settings.model_timeout_seconds):
            async for item in iterate():
                yield item
        self._record_debug_assistant(conversation_id, "".join(assistant_chunks))

    def _record_debug_turn_start(
        self,
        conversation_id: str,
        messages: list[SystemMessage | HumanMessage],
        route_context: dict[str, Any] | None,
    ) -> None:
        self._latest_conversation_id = conversation_id
        debug_context = self._debug_threads.setdefault(
            conversation_id,
            {
                "conversation_id": conversation_id,
                "model": self.settings.medusa_agent_model,
                "system_prompt": _debug_message(
                    role="system",
                    source="commerce_system_prompt",
                    content=COMMERCE_SYSTEM_PROMPT,
                ),
                "latest_route_context": {},
                "latest_accepted_intent": None,
                "latest_projection_version": None,
                "thread": [],
            },
        )
        debug_context["model"] = self.settings.medusa_agent_model
        debug_context["system_prompt"] = _debug_message(
            role="system",
            source="commerce_system_prompt",
            content=COMMERCE_SYSTEM_PROMPT,
        )
        debug_context["latest_route_context"] = _safe_route_context(route_context)
        debug_context["latest_accepted_intent"] = None
        debug_context["latest_projection_version"] = None
        debug_context["thread"].extend(_debug_message_from_langchain(message) for message in messages)

    def _record_debug_projection_update(
        self,
        conversation_id: str,
        accepted_projection_update: dict[str, Any],
    ) -> None:
        debug_context = self._debug_threads.get(conversation_id)
        if not debug_context:
            return
        debug_context["latest_route_context"] = _safe_route_context(
            accepted_projection_update.get("route_context")
        )
        debug_context["latest_accepted_intent"] = _safe_accepted_intent(accepted_projection_update)
        debug_context["latest_projection_version"] = _projection_version(accepted_projection_update)
        planning_context = accepted_projection_update.get("planning_context")
        if isinstance(planning_context, dict):
            debug_context["thread"].append(
                _debug_message(
                    role="system",
                    source="routedeck_planning_context",
                    content=planning_context_message(planning_context),
                )
            )

    def _record_debug_assistant(self, conversation_id: str, content: str) -> None:
        if not content:
            return
        debug_context = self._debug_threads.get(conversation_id)
        if not debug_context:
            return
        debug_context["thread"].append(
            _debug_message(role="assistant", source="assistant", content=content)
        )


chat_service = ChatService()


def _agent_messages(
    message: str,
    route_context: dict[str, Any] | None,
    settings: Settings,
) -> list[SystemMessage | HumanMessage]:
    messages: list[SystemMessage | HumanMessage] = []
    if route_context:
        projection = build_runtime_medusa_projection(
            path=_string_value(route_context.get("path"), "/"),
            surface_id=_optional_string_value(route_context.get("surface_id")),
            settings=settings,
        )
        context = build_planning_context(projection)
        messages.append(SystemMessage(content=planning_context_message(context)))
    messages.append(HumanMessage(content=message))
    return messages


def _string_value(value: Any, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


def _optional_string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _empty_debug_context(model: str) -> dict[str, Any]:
    return {
        "conversation_id": None,
        "model": model,
        "system_prompt": _debug_message(
            role="system",
            source="commerce_system_prompt",
            content=COMMERCE_SYSTEM_PROMPT,
        ),
        "latest_route_context": {},
        "latest_accepted_intent": None,
        "latest_projection_version": None,
        "thread": [],
    }


def _debug_message(*, role: str, source: str, content: str) -> dict[str, str]:
    return {
        "role": role,
        "source": source,
        "content": content,
    }


def _debug_message_from_langchain(message: SystemMessage | HumanMessage) -> dict[str, str]:
    if isinstance(message, SystemMessage):
        return _debug_message(
            role="system",
            source="routedeck_planning_context",
            content=str(message.content),
        )
    return _debug_message(role="user", source="user", content=str(message.content))


def _safe_route_context(route_context: dict[str, Any] | None) -> dict[str, str]:
    if not route_context:
        return {}
    safe: dict[str, str] = {}
    path = route_context.get("path")
    surface_id = route_context.get("surface_id")
    if isinstance(path, str):
        safe["path"] = path
    if isinstance(surface_id, str):
        safe["surface_id"] = surface_id
    return safe


def _safe_accepted_intent(accepted_projection_update: dict[str, Any] | None) -> dict[str, Any] | None:
    if not accepted_projection_update:
        return None
    return {
        "source": accepted_projection_update.get("source"),
        "intent": accepted_projection_update.get("intent"),
        "reason": accepted_projection_update.get("reason"),
        "route_context": accepted_projection_update.get("route_context"),
        "surface_intent": accepted_projection_update.get("surface_intent"),
    }


def _projection_version(accepted_projection_update: dict[str, Any] | None) -> int | None:
    if not accepted_projection_update:
        return None
    version = accepted_projection_update.get("projection_version")
    return version if isinstance(version, int) else None
