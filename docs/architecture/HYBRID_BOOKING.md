# Hybrid booking - Phase 6A

Appointments retain four separate timestamp facts. `booked_start_time` and
`booked_end_time` preserve the agreed slot. `actual_start_time` is recorded only on
start; `actual_end_time` is recorded on completion. Existing `start_time`/`end_time`
remain the current planning/execution interval used by capacity reads and legacy UI.
Early or late starts revalidate a complete duration without overwriting booked facts.

Migration c4e780bd219a copies the interval available in legacy rows into booked
fields. Historical actual timestamps remain null. Previously overwritten original
times cannot be recovered from these rows; the migration makes no reconstruction
claim. SQLite/PostgreSQL round-trip tests preserve a seeded legacy appointment and
verify schema parity. Booking lifecycle tests verify booked facts survive start and
execution timestamps distinguish completion from cancellation/no-show.

`PATCH /api/v1/appointments/{id}/confirm` transitions scheduled to confirmed under
the institute lock. Confirmed retries return the current booking without changing
its interval or reservation. Other states reject confirmation; existing booking
RBAC/tenant checks run before mutation. HTTP tests cover replay, reservation/booked
fact preservation, foreign tenant, missing booking and cancellation rejection.

`PATCH /api/v1/appointments/{id}` modifies scheduled/confirmed bookings. Slot changes
revalidate qualifications, employee sessions/appointments, assigned walk-ins and
resources under the institute lock. Resource matching excludes only the booking's
old reservation; failures retain the old interval. Moves retain duration snapshots
unless the service changes and update the agreed booked slot. Execution/final states
cannot be edited. Metadata fields support explicit clearing of phone/notes, while
required fields cannot be cleared. Appointment routes require an exact token tenant.
HTTP tests cover conflicts, replay, metadata, invalid states and tenant rejection;
a PostgreSQL race proves that two moves cannot take the same room interval.

The operator panel now offers confirmation and reuses its booking form for scheduled
or confirmed appointment edits. Failed saves preserve fields and show a retryable
error; successful saves return to creation. Date/time prefill uses local date and
time consistently. The App sends edits through the guarded PATCH endpoint. Component
tests cover confirmation visibility and movement failure/retry; these are JSDOM
checks, not real browser/tablet evidence.

`booking_events` now records creation, modification, confirmation, arrival, start,
completion, no-show and cancellation in the same transaction as operational state.
Events include operator, occurrence time and before/after operational snapshots.
They omit names, phone numbers and notes. Matching retries/no-op modifications do
not duplicate events; rejected moves create none. Injected commit failure proves
booking, resource interval and history rollback together. Migration d5f890ce320b
creates an empty history table; it does not invent events for legacy appointments.

Named-customer reservations use the authenticated operator booking workflow. The
canonical Phase 6 text does not specify a public self-service portal. The form sends
a creation replay key and retains it after failure, replacing it for changed/new
intent. Backend tenant/key uniqueness and a normalized creation fingerprint recover
the existing booking without allocating another resource or writing another event.
Changed facts with the same key reject; retries after lifecycle changes return the
current booking. Authorization runs first. Optional keys preserve older callers.
PostgreSQL simultaneous duplicate requests prove one booking/resource/event; client
tests prove key retention after failure and replacement after success. Migration
e6a901df431c preserves legacy rows and passes SQLite/PostgreSQL parity/round-trips.

Overdue active sessions/appointments have unknown remaining occupancy and block
creation or movement even into a later slot. Finishing restores capacity. Starting
cannot overlap another in-progress appointment. Parameterized HTTP cases exercise
both overdue sources and creation/movement recovery.

## Phase 6 canonical functional gates

| Gate | Evidence | Result |
| --- | --- | --- |
| HYBRID_BOOKING | Named customer create/confirm/edit/cancel workflow, operator controls, execution facts and atomic history | PASS |
| BOOKING_CREATE | Creation replay, invalid-input/tenant guards, interval checks, SQLite/PostgreSQL migration parity | PASS |
| BOOKING_MOVE | Resource/employee/walk-in guards, failed-move preservation, rollback injection, PostgreSQL competing-move race | PASS |
| BOOKING_CANCEL | HTTP lifecycle releases capacity; history and state commit together | PASS |
| RESOURCE_RESERVATION | Shared pool, full-duration matching, quantity/capability/tenant cases and PostgreSQL resource races | PASS |
| COEXISTENCE_WALKIN_BOOKING | Assigned walk-in and service/extension collision checks; PostgreSQL cross-operation races; overdue unknown-capacity recovery | PASS |

Phase 6 functional gates are closed within the canonical authenticated operator
reservation workflow. A public self-service portal is not specified or claimed.
Real browser/tablet UX and load validation remain separate open gates; Phase 7 must
verify real-time synchronization and reconnection rather than infer them from these
transaction tests.
