from __future__ import annotations

import sqlite3

import pytest
from cryptography.fernet import Fernet
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.session import (
    Location,
    PrivateSessionState,
    RouteDeckSession,
)
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.session import SESSION_SCHEMA_VERSION
from routedeck_sqlite import FernetSensitiveCodec, SqliteSessionStore
from routedeck_langgraph.conversation import extract_conversation_turns


@pytest.mark.asyncio
async def test_older_session_schema_is_rejected_before_state_deserialization(
    tmp_path,
) -> None:
    database_path = tmp_path / "schema-compatibility.sqlite"
    key = Fernet.generate_key()
    first = await SqliteSessionStore.open(
        database_path,
        instance_id="schema-writer",
        codec=FernetSensitiveCodec(key),
    )
    try:
        await first.create(
            RouteDeckSession(
                session_id="schema-session",
                schema_version=SESSION_SCHEMA_VERSION,
                navgraph_version="navgraph-version",
                session_version=1,
                projection_version=1,
                event_cursor=0,
                next_history_entry_id=2,
                current=Location(node_id="entry", entry_id=1),
                private_state=PrivateSessionState(),
            )
        )
    finally:
        await first.close()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE sessions SET schema_version = ? WHERE session_id = ?",
            (SESSION_SCHEMA_VERSION - 1, "schema-session"),
        )

    reopened = await SqliteSessionStore.open(
        database_path,
        instance_id="schema-reader",
        codec=FernetSensitiveCodec(key),
    )
    try:
        with pytest.raises(SessionStoreError) as captured:
            await reopened.load("schema-session")
        assert captured.value.code is SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_tool_call_preamble_and_arguments_do_not_enter_plaintext_state(
    tmp_path,
) -> None:
    sentinel = "private-buyer-tool-input-sentinel"
    user_turn = FinalizedConversationTurn(
        turn_id="user-turn",
        role=ConversationRole.USER,
        content="Run the safe tool.",
        request_id="chat-tool-privacy",
    )
    extracted = extract_conversation_turns(
        (
            HumanMessage(content=user_turn.content, id=user_turn.turn_id),
            AIMessage(
                content=sentinel,
                tool_calls=[
                    {
                        "id": "private-tool-call",
                        "name": "safe.tool",
                        "args": {"buyer_input": sentinel},
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="safe observation",
                name="safe.tool",
                status="success",
                tool_call_id="private-tool-call",
            ),
        ),
        current_user_turn=user_turn,
        id_factory=lambda _kind: "tool-turn",
    )
    database_path = tmp_path / "tool-history-privacy.sqlite"
    key = Fernet.generate_key()
    store = await SqliteSessionStore.open(
        database_path,
        instance_id="tool-history-writer",
        codec=FernetSensitiveCodec(key),
    )
    try:
        await store.create(
            RouteDeckSession(
                session_id="tool-history-session",
                schema_version=SESSION_SCHEMA_VERSION,
                navgraph_version="navgraph-version",
                session_version=1,
                projection_version=1,
                event_cursor=0,
                next_history_entry_id=2,
                current=Location(node_id="entry", entry_id=1),
                conversation=extracted.turns,
                private_state=PrivateSessionState(),
            )
        )
        reloaded = await store.load("tool-history-session")
        reloaded_call = reloaded.state.conversation[-1].tool_call
        assert reloaded_call is not None
        assert reloaded_call.assistant_content == sentinel
        assert reloaded_call.arguments["buyer_input"] == sentinel
    finally:
        await store.close()

    with sqlite3.connect(database_path) as connection:
        state_json = connection.execute(
            "SELECT state_json FROM sessions WHERE session_id = ?",
            ("tool-history-session",),
        ).fetchone()[0]
    assert sentinel not in str(state_json)
