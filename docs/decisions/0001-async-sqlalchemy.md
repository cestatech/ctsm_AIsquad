# ADR-0001: Use Async SQLAlchemy for All Database Operations

**Date:** 2026-06-02
**Status:** Accepted
**Authors:** architect-agent
**Reviewers:** backend-agent, database-agent

---

## Context

The Celerius platform needs a database access layer for PostgreSQL. Two approaches are viable: synchronous SQLAlchemy (traditional) or async SQLAlchemy 2.0. FastAPI is an async-native framework built on ASGI. Clinical trial platforms can have long-running operations (AI generation, validation runs) that would block synchronous workers.

---

## Decision

We will use async SQLAlchemy 2.0 with `asyncpg` driver for all database operations. All service and repository methods will be `async def`. Sessions will be managed via `AsyncSession` with `async_session_factory`.

---

## Consequences

### Positive
- Consistent with FastAPI's async model — no thread pool overhead for DB calls
- Better throughput under concurrent requests (multiple users working simultaneously)
- Non-blocking I/O allows AI generation jobs to run without blocking API requests
- Modern SQLAlchemy 2.0 API is cleaner and better typed

### Negative
- Steeper learning curve for developers unfamiliar with async Python
- Some SQLAlchemy plugins and utilities are sync-only (must wrap carefully)
- Debugging async code is more complex

---

## Alternatives Considered

### Alternative A: Synchronous SQLAlchemy with thread pool
**Why rejected:** FastAPI's built-in thread pool (`run_in_executor`) adds overhead and complexity. Mixing sync/async at the DB layer creates subtle bugs with session management.

### Alternative B: Tortoise ORM
**Why rejected:** Less mature ecosystem, fewer available extensions, smaller community for clinical-domain use cases.

---

## References

- SQLAlchemy 2.0 async documentation
- FastAPI async database guide
