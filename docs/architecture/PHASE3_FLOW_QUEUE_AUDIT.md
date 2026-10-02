# Phase 3: Flow and queue audit

## Existing domain to retain

`QueueTicket` is already the walk-in aggregate. Optional `customer_id` and
`subscription_id` preserve anonymous arrivals; `arrival_time` is server-generated.
`TicketLine.duration_minutes` snapshots `Service.duration_min` at creation.
Planning reserves one `ServiceSession` for the sum of all ticket lines, marks the
employee busy, then releases them and moves the ticket to checkout. Existing
ticket-manager RBAC and institute checks remain the API boundary.

`GET /tickets/waiting` is a compatibility endpoint: it includes waiting,
assigned, in-progress and checkout tickets. It must keep that behavior.
Employees already support available, busy, pause, absent and offline.

## Findings

- Arrival sorting has no tie breaker; frontend sorting also uses stale estimates.
- Ticket numbers count only active tickets, so cancellation/payment reuse numbers.
- Creation commits the ticket and each line separately; a retry can find a partial ticket.
- Assignment checks active work but permits multiple assigned tickets per employee
  and does not check the complete duration against an imminent appointment.
- Assignment replay revalidates availability, potentially rejecting an already
  applied action. Creation keys do not reject changed payloads.
- Cancellation is already replay-safe but has no timestamp or domain event.
- Employee create accepts arbitrary states; pausing ignores assigned reservations.
- WebSocket exists; durable queue events do not. Local creation refresh is present.
- The full ticket wizard opens on identity and takes four steps; a basic anonymous
  arrival can start at service selection and submit directly.

## Phase 3 contract and checkpoints

1. Audit and baseline verification.
2. Extend the existing ticket domain: lifecycle policy, atomic creation, institute
   transaction lock, arrival/id FIFO ordering and derived one-based queue position,
   assignment/release/cancellation, duration conflict checks, durable events and
   replay tests. Keep all planning and checkout states and endpoints.
3. Fast anonymous arrival UX, stable retry keys and immediate queue visibility;
   complete regression and migration checks and close the phase.

Waiting/assigned tickets occupy FIFO positions. Starting service, cancellation
and payment remove a ticket from the waiting queue; active operational tickets
remain visible through the compatibility endpoint. Assignment reserves an
employee without changing the existing persisted `available` state, so planning
and the current start action remain compatible. Other tickets cannot reserve or
start with that employee until the reservation is released or cancelled.

Events are transactionally stored facts, scoped by institute and ticket. Replays
must not duplicate lines, sessions or transition events. Events are the minimal
foundation for subsequent capacity/wait recalculation; existing estimates remain
legacy hints. The full Waiting Time Engine, resource allocation and scheduling
optimization belong to the subsequent phases.

UX acceptance target: open arrival, choose service, add to queue (three clicks
for the first category). No customer identity is mandatory. The under-15-second
target is a workflow design target; field timing requires operator validation.
