# Flow and queue domain (Phase 3)

The existing `QueueTicket` remains the walk-in aggregate. A basic arrival only
requires an institute and one or more catalog services. Client identity and
creator employee identification are optional. Arrival is stamped by the server.

## Lifecycle

`waiting -> assigned -> in_progress -> ready_for_checkout -> in_checkout -> paid`

Direct `waiting -> in_progress` and `ready_for_checkout -> paid` remain supported.
An assigned ticket may return to waiting. Waiting, assigned and checkout tickets
may be cancelled; active services must finish first. Paid and cancelled tickets
are terminal. Assignment is reserved for one employee and one queued ticket.
Reservations must be released before the employee takes a different ticket or
goes on pause/offline/absent. Persisted employee states remain available, busy,
pause, absent and offline, preserving planning compatibility.

Queue order is `(arrival_time ASC, id ASC)` within one institute. Waiting and
assigned tickets share compact one-based `queue_position`; all other states have
no queue position. Assignment does not reorder an arrival. The existing
`GET /tickets/waiting` continues returning the entire active operational flow,
including service and checkout. Ticket numbers include historical tickets.

## Duration and safety

Ticket lines snapshot the catalog's standard `duration_min`. Planning uses the
sum of `duration_minutes * quantity` for its single session. Later catalog edits
do not change an existing ticket's duration. Assignment and service start reject
overlap with an active or imminent employee appointment for that complete window.

PostgreSQL mutations acquire an institute row lock before refreshing aggregate
state. Creation commits the ticket, all lines and arrival event together. An
institute-scoped idempotency key identifies one creation intent; a fingerprint
rejects a changed payload and survives checkout line corrections. Exact state
command replays preserve timestamps, session IDs, totals and transition events.
Checkout line edits and extensions remain additive commands, as before.

## Events and interfaces

Durable `QueueEvent` facts share the state transaction: arrived, assigned,
unassigned, cancelled, service_started, service_finished, checkout_started and
paid. Service extensions emit service_extended. Events have institute/ticket IDs,
employee context, previous/new status and occurrence time. IDs provide stable
event order. `GET /tickets/{ticket_id}/events` is paginated and enforces the same
RBAC and institute checks; `PATCH /tickets/{ticket_id}/unassign` releases a
reservation and records an audit action.

These facts and duration snapshots are the Waiting Time foundation. Existing
estimated start times remain legacy hints; this phase does not introduce the full
Waiting Time Engine, automatic capacity projections or resource allocation.

## Migration and verification

Before running an existing database with this version, apply revision
`6f8c2d1a930b` from `backend` using `python -m alembic upgrade head` and the intended
`DATABASE_URL`. `create_all` alone cannot update existing ticket columns. Legacy
rows have nullable timestamps/fingerprints; historical events are not invented.

Automated coverage includes anonymous creation, duration snapshots, FIFO ties,
compact positions, cancellation, reservation/release, unavailable employees,
imminent appointments, cross-institute/RBAC denial, atomic rollback and replay.
Migration tests cover SQLite upgrade/downgrade/upgrade, legacy preservation and
model parity, plus PostgreSQL SQL compilation. PostgreSQL runtime/concurrency
validation requires a responding PostgreSQL instance.

The operator authenticates once per session. HTTP and WebSocket requests carry
that token. Fast arrival is open, select service, add to queue; the returned ticket
is immediately inserted locally before the normal refresh. Component tests cover
submission/retry and login/logout. Real browser/tablet layout and operator timing
must be validated separately when a browser surface is available.
