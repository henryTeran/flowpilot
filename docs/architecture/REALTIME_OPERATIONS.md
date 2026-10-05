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
revision increments. The opt-in `test_live_realtime_7e.py` additionally starts two
owned Uvicorn processes with inherited loopback listeners against a random test
schema. An HTTP queue write on one reaches a WebSocket on the other; a foreign
tenant commit and rolled-back local change do not notify that connection. After
closing and reconnecting the transport, REST recovers offline writes and new
notices arrive on the replacement connection. The live protocol/revision bundle
passes two tests. Processes stop before the fixture removes its schema, including
on test failure. Run this integration test in the Linux PostgreSQL test runner.

REALTIME_SYNC is PASS at this two-process protocol scope. Client retry/heartbeat
behavior is separately covered by deterministic frontend tests; reconnecting this
protocol client does not prove browser recovery or tablet UX. Full RECONNECT and
TABLET_UX remain open pending actual browser evidence and the live-board audit.

Operational REST refreshes use a context/sequence gate: only the newest request
for the selected institute and unchanged operator token can apply data or errors.
Changing institutes clears operational views and selections. Employee selection
does not recreate the WebSocket. Twenty frontend tests and the production build
pass, including an App integration test that resolves old-institute requests after
the new board has loaded. This remains component evidence, not tablet validation.

All asynchronous App actions also capture an institute generation and operator
token. Periodic refreshes do not invalidate an action. Leaving and returning to an
institute does: late results/errors cannot alter the replacement view, and a pending
assignment cannot continue into a start after a context change. Already submitted
server writes retain their normal transactional behavior. Twenty-two frontend tests
and the production build pass, including the delayed-assignment App scenario.

## Live-board audit at Phase 7F

| Canonical operation/state | Existing behavior | Remaining verification/work |
| --- | --- | --- |
| EXPECTED / ARRIVED / NO_SHOW | Booking scheduled/confirmed, arrived, no_show; booking panel actions | Browser UX open |
| WAITING / IN_SERVICE | Walk-in waiting/assigned, in_progress; booking in_progress | Existing capacity/start tests; browser UX open |
| FINISH | Walk-in releases capacity and becomes ready_for_checkout; booking becomes completed and releases resources | Booking-to-checkout handoff missing |
| PAYMENT_PENDING / COMPLETED / PAY | Walk-in ready_for_checkout/in_checkout, paid; checkout attribution and replay tests | Booking must enter the checkout flow before claiming complete coverage |
| PAUSE / EXTEND | Employee pause/dispo; session +5/+10, transactional extension replay | Pause is employee availability, not a suspended treatment; browser UX open |
| Live recalculation | REST planning/availability and deterministic joint queue/resource projections, committed revision invalidation | Combined live action/recalculation audit remains open |

The booking `completed` status currently means treatment finished, not evidence of
payment. No payment/commercial completion is inferred from it. LIVE_BOARD remains
open until the booking handoff and combined workflow evidence are implemented.
