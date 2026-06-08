from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from routedeck_core import RouteDeckEvent

from core.config import Settings
from core.protocol import (
    agent_end,
    agent_start,
    chunk_text,
    error,
    message_delta,
    routedeck_event,
    stream_end,
    stream_start,
)
from services.routedeck_provider import get_routedeck_runtime


logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, settings: Settings | None = None, graph: Any | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.graph = graph

    async def stream(
        self,
        message: str,
        conversation_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        conversation_id = conversation_id or f"conv-{uuid.uuid4().hex}"
        route_session_id = session_id or conversation_id

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
                async for item in self._stream_graph(message, conversation_id, route_session_id):
                    if isinstance(item, RouteDeckEvent):
                        yield routedeck_event(item.model_dump(mode="json"))
                    else:
                        yield message_delta(item)
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
        route_session_id: str,
    ) -> AsyncGenerator[str | RouteDeckEvent, None]:
        graph = self.graph
        runtime = get_routedeck_runtime(settings=self.settings)
        pending_route_events: list[RouteDeckEvent] = []
        if graph is None:
            from services import graph_builder

            graph = graph_builder.build_agent_graph(
                self.settings,
                session_id=route_session_id,
                runtime=runtime,
                route_event_sink=pending_route_events.append,
            )

        config = {"configurable": {"thread_id": conversation_id}}
        from services.routedeck_prompt import build_routedeck_system_prompt

        route_deck_prompt = await build_routedeck_system_prompt(self.settings, session_id=route_session_id, runtime=runtime)
        messages = [
            SystemMessage(content=route_deck_prompt),
            HumanMessage(content=message),
        ]

        async def flush_route_events() -> AsyncGenerator[RouteDeckEvent, None]:
            while pending_route_events:
                yield pending_route_events.pop(0)

        async def iterate() -> AsyncGenerator[str | RouteDeckEvent, None]:
            async for event in graph.astream_events(
                {"messages": messages},
                config=config,
                version="v2",
            ):
                async for route_event in flush_route_events():
                    yield route_event
                if event.get("event") != "on_chat_model_stream":
                    continue
                chunk = event.get("data", {}).get("chunk")
                content = chunk_text(getattr(chunk, "content", ""))
                if content:
                    yield content
            async for route_event in flush_route_events():
                yield route_event

        async with asyncio.timeout(self.settings.model_timeout_seconds):
            async for content in iterate():
                yield content


chat_service = ChatService()
