# Persistence And Recovery

## Purpose

`routedeck_sqlalchemy` is the durable authority behind the core session-store
port. It supports explicit SQLite and PostgreSQL URLs with the same ORM model,
fencing, journals, events, encrypted private blobs, retention, and restart
semantics.

## Owner Files

- `routedeck_sqlalchemy/application_runtime.py`
- `routedeck_sqlalchemy/store.py` and `store_parts/`
- `routedeck_sqlalchemy/{database,models,sessions,turns,operations,commits}.py`
- `routedeck_sqlalchemy/{codec,lease,recovery,serialization,runtime}.py`

## Interfaces And Invariants

- `open_sqlalchemy_routedeck_runtime(...)` opens the store/codec and delegates
  generic assembly to `build_routedeck_runtime(...)`.
- `SqlAlchemySessionStore` is the canonical facade; focused transaction classes
  are internal responsibility owners, not alternate stores.
- One application lease fences unsupported multi-worker use.
- Session creation and all mutations retain request identity and reject
  conflicting replay.
- Operation attempts, reviews, execution claims/results, events, conversation,
  private blobs, and tombstones commit through explicit transactions.
- Startup recovers abandoned turns as interrupted in bounded batches; it never
  invents tool success or silently replays external work.
- A supplied database, key, store, or invariant failure propagates. No alternate
  database or codec is selected.

## Evidence

```powershell
python -m pytest tests/sqlalchemy tests/sqlite/test_persistent_runtime_smoke.py -q
```

Update this document for schema, dialect, lease, journal, transaction, reopen,
retention, encryption, or recovery changes.
