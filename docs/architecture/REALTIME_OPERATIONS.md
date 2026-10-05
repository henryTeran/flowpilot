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

The server still provides ping/pong rather than verified committed-change
synchronization. REALTIME_SYNC and the full RECONNECT gate remain open; TABLET_UX is
blocked by unavailable CUA browser surfaces. The connection manager is process-local
and is not evidence of delivery across multiple workers.
