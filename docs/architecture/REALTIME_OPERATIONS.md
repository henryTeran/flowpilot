# Live operations - Phase 7A

Planning WebSockets require an authenticated ticket-manager role and an exact token
institute match. A missing tenant is not a cross-institute authorization bypass.
Rejected handshakes close with code 1008. Route teardown removes the socket even if
the receive loop fails unexpectedly; empty institute connection groups are removed.

Broadcast iterates a snapshot of connections. Closed/disconnected transport failures
remove only the failed socket and do not prevent healthy clients in the institute
from receiving the update. Other institutes receive no messages. Seven targeted
tests cover handshake scope/role checks and connection lifecycle/delivery isolation.

The current runtime still provides ping/pong rather than verified committed-change
synchronization. The client has no reconnect loop. REALTIME_SYNC and RECONNECT remain
open; TABLET_UX remains blocked by unavailable CUA browser surfaces. The connection
manager is process-local and is not evidence of delivery across multiple workers.
