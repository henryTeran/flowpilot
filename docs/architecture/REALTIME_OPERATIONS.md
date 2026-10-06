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
| FINISH | Walk-in and booking release capacity and create ready_for_checkout; booking has a durable checkout_ticket_id | Booking completion replay, failure rollback and PostgreSQL competing finishes pass |
| PAYMENT_PENDING / COMPLETED / PAY | Linked booking and walk-in tickets use ready_for_checkout/in_checkout, paid; cashier/service attribution and replay | App finish-to-identification-to-caisse scenario passes; external provider settlement is Phase 9 |
| PAUSE / EXTEND | Employee pause/dispo; session +5/+10, transactional extension replay | Pause is employee availability, not a suspended treatment; browser UX open |
| Live recalculation | REST planning/availability and deterministic joint queue/resource projections, committed revision invalidation | Combined two-process action/recalculation scenario passes; browser UX open |

The booking `completed` status means treatment finished, not evidence of payment.
The linked ticket is the checkout/payment record. Legacy completed bookings stay
unlinked; no charge is fabricated from historical treatment status. The combined
live action/recalculation evidence below establishes functional protocol coverage;
browser UX remains open.

## Phase 7H live action/recalculation evidence

The two-process PostgreSQL suite passes both protocol scenarios. Its combined
scenario performs employee pause/resume, two walk-in arrivals, assignment, start,
extension, finish, checkout and payment, followed by booking create/confirm/arrive/
start/finish/payment and no-show. Every write produces a newer committed revision
on the reader server's WebSocket before REST verification on that reader. It checks
employee availability, active ownership, shared-room reservation lifecycle, the
extended planning interval, the second ticket's resource-constrained projection,
released capacity, linked booking checkout and recorded revenue.

LIVE_BOARD and LIVE_RECALCULATION pass at this authenticated HTTP/WebSocket scope.
Recorded payment means the existing operational payment record; external provider
settlement is still Phase 9. RECONNECT has protocol recovery, deterministic client lifecycle evidence and
controlled real-browser offline/native-close recovery. Physical TABLET_UX remains
open. Phase 7 is therefore not fully closed. Independent Phase 8 work can proceed
without claiming tablet or production readiness.


The backend-connected Edge suite additionally uses two independently authenticated
pages. Real planning.changed frames precede the observer displaying a new arrival.
An offline observer has its native socket closed, misses another committed arrival,
then opens a new real connection and resynchronizes the missing ticket over REST.
The native constructor is instrumented to retain socket references, without mocking
handshakes, messages, API responses or session tokens. Desktop and touch-enabled
tablet-landscape cases pass within eight browser tests. These are controlled
transport interruptions on disposable single-process SQLite, not a physical tablet
or live multi-server production outage.

Browsers explicitly use Europe/Zurich. Session response dates now identify the
UTC instant when SQLite has dropped timezone metadata from domain UTC timestamps;
aware values and absent real end remain unchanged. This prevents local browser
interpretation from hiding an active session outside the visible timeline.
Seventeen focused backend serialization/workflow tests and the combined browser
suite pass. Stored timestamps, durations and business decisions are not rewritten.

Actual PostgreSQL two-process protocol and timestamp serialization bundle: six
passed after the response correction. This supplements the browser fixture;
PostgreSQL-aware instants retain their original instant.
