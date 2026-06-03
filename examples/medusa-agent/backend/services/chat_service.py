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


logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, settings: Settings | None = None, graph: Any | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.graph = graph

    async def stream(
        self,
        message: str,
        conversation_id: str | None = None,
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
                async for chunk in self._stream_graph(message, conversation_id):
                    yield message_delta(chunk)
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
    ) -> AsyncGenerator[str, None]:
        graph = self.graph
        if graph is None:
            from services.graph_builder import build_agent_graph

            graph = build_agent_graph(self.settings, session_id=conversation_id)

        config = {"configurable": {"thread_id": conversation_id}}
        from services.routedeck_prompt import build_routedeck_system_prompt

        route_deck_prompt = await build_routedeck_system_prompt(self.settings, session_id=conversation_id)
        messages = [
            SystemMessage(content=route_deck_prompt),
            HumanMessage(content=message),
        ]

        async def iterate() -> AsyncGenerator[str, None]:
            async for event in graph.astream_events(
                {"messages": messages},
                config=config,
                version="v2",
            ):
                if event.get("event") != "on_chat_model_stream":
                    continue
                chunk = event.get("data", {}).get("chunk")
                content = chunk_text(getattr(chunk, "content", ""))
                if content:
                    yield content

        async with asyncio.timeout(self.settings.model_timeout_seconds):
            async for content in iterate():
                yield content


chat_service = ChatService()
