from __future__ import annotations


SCHEMA_VERSION = 2

CREATE_MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    applied_at TEXT NOT NULL
)
"""

SCHEMA_V1_STATEMENTS = (
    """
    CREATE TABLE application_lease (
        slot INTEGER PRIMARY KEY CHECK (slot = 1),
        instance_id TEXT NOT NULL CHECK (length(instance_id) > 0),
        fencing_token INTEGER NOT NULL CHECK (fencing_token > 0),
        heartbeat_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        released_at TEXT
    )
    """,
    """
    CREATE TABLE sessions (
        session_id TEXT PRIMARY KEY CHECK (length(session_id) > 0),
        schema_version INTEGER NOT NULL CHECK (schema_version > 0),
        navgraph_version TEXT NOT NULL CHECK (length(navgraph_version) > 0),
        session_version INTEGER NOT NULL CHECK (session_version >= 0),
        projection_version INTEGER NOT NULL CHECK (projection_version >= 0),
        event_cursor INTEGER NOT NULL CHECK (event_cursor >= 0),
        state_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_accessed_at TEXT NOT NULL,
        idle_expires_at TEXT NOT NULL,
        absolute_expires_at TEXT NOT NULL,
        completed_at TEXT,
        expires_at TEXT NOT NULL,
        owner_fencing_token INTEGER NOT NULL CHECK (owner_fencing_token > 0)
    )
    """,
    "CREATE INDEX sessions_expiry ON sessions(expires_at, session_id)",
    """
    CREATE TABLE session_tombstones (
        session_id TEXT PRIMARY KEY,
        expired_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE turn_leases (
        session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
        request_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        owner_kind TEXT NOT NULL,
        parent_turn_id TEXT,
        capability_hash TEXT NOT NULL,
        fencing_token INTEGER NOT NULL CHECK (fencing_token > 0),
        acquired_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE active_child_attempts (
        session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
        parent_request_id TEXT NOT NULL,
        request_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        acquired_at TEXT NOT NULL,
        UNIQUE(session_id, request_id)
    )
    """,
    """
    CREATE TABLE operation_attempts (
        attempt_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        request_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        record_json TEXT NOT NULL,
        review_id TEXT,
        status TEXT NOT NULL,
        fencing_token INTEGER NOT NULL CHECK (fencing_token > 0),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(session_id, request_id)
    )
    """,
    "CREATE INDEX operation_attempts_review ON operation_attempts(session_id, review_id)",
    """
    CREATE TABLE operation_journal (
        journal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        attempt_id TEXT NOT NULL REFERENCES operation_attempts(attempt_id) ON DELETE CASCADE,
        phase TEXT NOT NULL,
        record_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        fencing_token INTEGER NOT NULL CHECK (fencing_token > 0)
    )
    """,
    "CREATE INDEX operation_journal_attempt ON operation_journal(attempt_id, journal_id)",
    """
    CREATE TABLE reviews (
        review_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        attempt_id TEXT NOT NULL REFERENCES operation_attempts(attempt_id) ON DELETE CASCADE,
        record_json TEXT NOT NULL,
        resolution TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX reviews_session ON reviews(session_id, review_id)",
    """
    CREATE TABLE execution_claims (
        attempt_id TEXT PRIMARY KEY REFERENCES operation_attempts(attempt_id) ON DELETE CASCADE,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        request_id TEXT NOT NULL,
        capability_hash TEXT NOT NULL,
        fencing_token INTEGER NOT NULL CHECK (fencing_token > 0),
        status TEXT NOT NULL,
        claimed_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE execution_results (
        result_id TEXT PRIMARY KEY,
        attempt_id TEXT NOT NULL UNIQUE REFERENCES operation_attempts(attempt_id) ON DELETE CASCADE,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        result_json TEXT NOT NULL,
        record_json TEXT NOT NULL,
        result_fingerprint TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE events (
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        cursor INTEGER NOT NULL CHECK (cursor > 0),
        event_id TEXT NOT NULL UNIQUE,
        event_type TEXT NOT NULL,
        session_version INTEGER NOT NULL CHECK (session_version >= 0),
        projection_version INTEGER CHECK (projection_version >= 0),
        created_at TEXT NOT NULL,
        event_json TEXT NOT NULL,
        PRIMARY KEY(session_id, cursor)
    )
    """,
    "CREATE INDEX events_retention ON events(session_id, created_at, cursor)",
    """
    CREATE TABLE private_blobs (
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        form_id TEXT NOT NULL,
        ciphertext BLOB NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(session_id, form_id)
    )
    """,
    """
    CREATE TABLE conversation_blobs (
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        turn_id TEXT NOT NULL,
        ciphertext BLOB NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(session_id, turn_id)
    )
    """,
)

SCHEMA_V2_STATEMENTS = (
    """
    CREATE TABLE session_creation_requests (
        request_id TEXT PRIMARY KEY CHECK (length(request_id) > 0),
        request_fingerprint TEXT NOT NULL CHECK (length(request_fingerprint) > 0),
        session_id TEXT NOT NULL UNIQUE REFERENCES sessions(session_id) ON DELETE CASCADE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE mutation_journal (
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        request_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL CHECK (length(request_fingerprint) > 0),
        mutation_kind TEXT NOT NULL CHECK (length(mutation_kind) > 0),
        status TEXT NOT NULL CHECK (length(status) > 0),
        result_json TEXT NOT NULL,
        committed_session_version INTEGER NOT NULL CHECK (committed_session_version >= 0),
        committed_projection_version INTEGER NOT NULL CHECK (committed_projection_version >= 0),
        committed_event_cursor INTEGER NOT NULL CHECK (committed_event_cursor >= 0),
        created_at TEXT NOT NULL,
        PRIMARY KEY(session_id, request_id)
    )
    """,
)


__all__ = [
    "CREATE_MIGRATION_TABLE",
    "SCHEMA_V1_STATEMENTS",
    "SCHEMA_V2_STATEMENTS",
    "SCHEMA_VERSION",
]
