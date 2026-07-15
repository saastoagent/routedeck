from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from routedeck_core.contracts.session import RouteDeckSession
from routedeck_core.ports import SensitiveCodec
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode
from routedeck_core.state.session import SESSION_SCHEMA_VERSION

from .models import ConversationBlobRow, PrivateBlobRow, SessionRow


@dataclass(frozen=True)
class SerializedSession:
    state_json: str
    conversation_blobs: dict[str, bytes]


def serialize_session(
    state: RouteDeckSession,
    codec: SensitiveCodec,
) -> SerializedSession:
    payload = state.model_dump(mode="json")
    conversation_payload = payload.get("conversation")
    if not isinstance(conversation_payload, list):
        raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
    encrypted: dict[str, bytes] = {}
    references: list[str] = []
    for index, turn in enumerate(state.conversation):
        item = conversation_payload[index]
        if not isinstance(item, dict) or item.get("turn_id") != turn.turn_id:
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        sensitive_turn = json.dumps(
            {
                "format": "routedeck-conversation-turn-v2",
                "content": turn.content,
                "tool_call": (
                    turn.tool_call.model_dump(mode="json")
                    if turn.tool_call is not None
                    else None
                ),
                "tool_status": turn.tool_status,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        encrypted[turn.turn_id] = codec.encrypt(sensitive_turn)
        item["content"] = ""
        item["tool_call"] = None
        item["tool_status"] = None
        references.append(turn.turn_id)
    envelope = {
        "format": "routedeck-session-v1",
        "session": payload,
        "conversation_blob_refs": references,
    }
    return SerializedSession(
        state_json=json.dumps(
            envelope,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        conversation_blobs=encrypted,
    )


def deserialize_session(
    database: Session,
    row: SessionRow,
    codec: SensitiveCodec,
) -> RouteDeckSession:
    if row.schema_version != SESSION_SCHEMA_VERSION:
        raise SessionStoreError(SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED)
    try:
        envelope = json.loads(row.state_json)
    except (TypeError, json.JSONDecodeError) as error:
        raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE) from error
    if (
        not isinstance(envelope, dict)
        or envelope.get("format") != "routedeck-session-v1"
        or not isinstance(envelope.get("session"), dict)
        or not isinstance(envelope.get("conversation_blob_refs"), list)
    ):
        raise SessionStoreError(SessionStoreErrorCode.SESSION_UPGRADE_REQUIRED)
    payload = envelope["session"]
    conversation = payload.get("conversation")
    references = envelope["conversation_blob_refs"]
    if not isinstance(conversation, list) or len(conversation) != len(references):
        raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
    blobs = {
        blob.turn_id: blob.ciphertext
        for blob in database.scalars(
            select(ConversationBlobRow).where(
                ConversationBlobRow.session_id == row.session_id
            )
        )
    }
    for index, turn_id in enumerate(references):
        if not isinstance(turn_id, str) or turn_id not in blobs:
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        item = conversation[index]
        if not isinstance(item, dict) or item.get("turn_id") != turn_id:
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        try:
            sensitive_turn = json.loads(codec.decrypt(blobs[turn_id]).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SessionStoreError(
                SessionStoreErrorCode.PERSISTENCE_FAILURE
            ) from error
        if (
            not isinstance(sensitive_turn, dict)
            or sensitive_turn.get("format") != "routedeck-conversation-turn-v2"
            or not isinstance(sensitive_turn.get("content"), str)
            or not (
                sensitive_turn.get("tool_call") is None
                or isinstance(sensitive_turn.get("tool_call"), dict)
            )
            or not (
                sensitive_turn.get("tool_status") is None
                or sensitive_turn.get("tool_status") in ("success", "error")
            )
        ):
            raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
        item["content"] = sensitive_turn["content"]
        item["tool_call"] = sensitive_turn["tool_call"]
        item["tool_status"] = sensitive_turn["tool_status"]
    state = RouteDeckSession.model_validate(payload)
    metadata = (
        state.schema_version,
        state.navgraph_version,
        state.session_version,
        state.projection_version,
        state.event_cursor,
    )
    stored_metadata = (
        row.schema_version,
        row.navgraph_version,
        row.session_version,
        row.projection_version,
        row.event_cursor,
    )
    if metadata != stored_metadata:
        raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
    return state


def sync_conversation_blobs(
    database: Session,
    *,
    session_id: str,
    conversation: dict[str, bytes],
    now: datetime,
) -> None:
    existing = {
        row.turn_id: row
        for row in database.scalars(
            select(ConversationBlobRow).where(
                ConversationBlobRow.session_id == session_id
            )
        )
    }
    for turn_id, ciphertext in conversation.items():
        row = existing.pop(turn_id, None)
        if row is None:
            database.add(
                ConversationBlobRow(
                    session_id=session_id,
                    turn_id=turn_id,
                    ciphertext=ciphertext,
                    updated_at=now,
                )
            )
        else:
            row.ciphertext = ciphertext
            row.updated_at = now
    for row in existing.values():
        database.delete(row)


def sync_private_blobs(
    database: Session,
    *,
    session_id: str,
    form_ids: tuple[str, ...],
) -> None:
    statement = delete(PrivateBlobRow).where(PrivateBlobRow.session_id == session_id)
    if form_ids:
        statement = statement.where(PrivateBlobRow.form_id.not_in(form_ids))
    database.execute(statement)


__all__ = [
    "SerializedSession",
    "deserialize_session",
    "serialize_session",
    "sync_conversation_blobs",
    "sync_private_blobs",
]
