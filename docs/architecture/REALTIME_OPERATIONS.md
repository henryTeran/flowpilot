# Live operations - Phase 7A

Planning WebSockets require an authenticated ticket-manager role and an exact token
institute match. A missing tenant is not a cross-institute authorization bypass.
Rejected handshakes close with code 1008. Route teardown removes the socket even if
the receive loop fails unexpectedly; empty institute connection groups are removed.

Broadcast iterates a snapshot of connections. Closed/disconnected transport failures
remove only the failed socket and do not prevent healthy clients in the institute
from receiving the update. Other institutes receive no messages. Seven targeted
tests cover handshake scope/role checks and connection lifecycle/delivery isolation.

The client now uses `planningConnection.ts`: exponential retries capped at 30 seconds,
REST resynchronization on each successful open, 20-second pings with a 10-second
response watchdog, and teardown of sockets/timers when context changes. Obsolete
socket events cannot refresh or change status. A policy close code 1008 stops retries;
transport handshake failures reported as 1006 follow the capped retry policy.
`planning.changed` triggers a refresh; pong/malformed messages do not. Eighteen
frontend tests pass, including deterministic reconnect/heartbeat/cleanup scenarios.
These simulations are not real browser or network delivery evidence.

`planning_revisions` stores an atomic per-institute counter in the same transaction
as operational ORM writes. Flush hooks track scoped employees, queue lines/tickets,
sessions, bookings and resource facts. Global catalog changes invalidate all
institutes; the development bulk reset explicitly marks its scope. No-op ORM writes
and booking replay do not advance it. Rollback removes the marker change together
with business state. The counter may advance more than once within a transaction;
it is an invalidation revision, not a business event count or audit log.

Each WebSocket reads its tenant's committed revision at most once per second and
sends `planning.changed` when it differs. This is database-backed bounded polling,
not a process-local broadcast dependency. Read transactions are ended between polls
and queries run outside the event loop. Clients resynchronize through authenticated
REST; notices contain only event/revision. Disconnected clients recover via refresh
on reconnect. Database query load scales with connected sockets; production load
and optimization remain open.

Tests prove commit visibility, rollback/no-op/replay semantics, queue-to-WebSocket
delivery and tenant revision isolation. PostgreSQL concurrent workers cannot lose
revision increments. These are database/ASGI checks, not proof of two live server
processes or real browser reconnect. REALTIME_SYNC and full RECONNECT remain open
until that integration evidence is gathered; TABLET_UX remains blocked.
