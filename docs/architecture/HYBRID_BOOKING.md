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

## Phase 7 booking checkout handoff

Completing an arrived/in-progress booking creates one ready-for-checkout ticket
and one performed service line in the same transaction as execution facts, resource
release, employee status and booking history. The caller holds the institute lock;
the checkout primitive neither commits nor adds a waiting/capacity commitment.
`checkout_ticket_id` is a durable nullable foreign key with uniqueness. Repeating
completion returns the existing linked booking, including after its ticket is paid.
History records the link without names, phones or notes.

The line preserves the booking's planned duration and performing employee; its
passage price is read from the catalog at checkout preparation, as no booking price
snapshot existed previously. The cashier is independently attributed by checkout.
Commercial benefits/pricing and external settlement remain Phase 8/9 work. The
App's finish action refreshes and opens this ticket, requesting cashier identity
when necessary. Legacy finished bookings remain unlinked and are not rebilled.

Migration a8c123f653be passes SQLite/PostgreSQL round-trips and model parity;
PostgreSQL upgrade/check passes. Full local backend suite: 193 passed, 17 opt-in
PostgreSQL cases skipped. Booking checkout/move PostgreSQL bundle: four passed,
including competing finishes and failure after checkout flush. Frontend: 23 tests
and production build pass, including App finish-to-checkout identification. These
are protocol/component tests; actual browser/tablet validation remains open.


Real Edge + isolated backend coverage now creates and confirms a room-backed
appointment, then tries the same interval with another qualified employee. The
shared resource conflict is rejected without another appointment being created.
Cancellation releases the first reservation, permitting retry of the original
pending second form/key. Both test appointments are cancelled at completion.
Desktop/tablet-landscape cases pass within ten backend-connected browser tests.
The fixture explicitly configures one room requirement for Soin profond and does
not alter production resources. This is booking-to-booking resource contention,
not full walk-in/appointment coexistence or physical-tablet acceptance.

Appointment response timestamps restore explicit UTC metadata when SQLite has
dropped it from stored domain UTC instants. Current, booked and actual intervals
retain their original instant; aware offsets and absent optional fields remain
unchanged. Browser coverage verifies the displayed hour matches the local form
hour in Europe/Zurich. Eleven focused backend serialization/confirmation/move
tests and ten actual PostgreSQL move/serialization checks pass. No stored
interval or scheduling rule is rewritten.

Aware appointment inputs are also canonicalized to UTC before persistence. A
real HTTP/SQLite regression reproduced a +02:00 input being stored without its
offset and later misidentified; the corrected input preserves the exact instant.
This follows the existing domain UTC convention for naive stored dates and does
not reconstruct offsets already lost in historical SQLite records. Final focused
booking/session/input-offset/checkout bundle: 20 passed. PostgreSQL-enabled
move/serialization bundle: 11 passed, comprising two actual PostgreSQL move cases
and nine schema/SQLite timestamp cases.

Final full backend regression after the input/output timestamp corrections and
bounded Windows sharing-lock cleanup: 329 passed, 69 opt-in PostgreSQL skips.
The separate PostgreSQL-enabled bundle remains the evidence for real database
move cases; the skipped local cases are not counted as PostgreSQL validation.
The first full attempt had 328 assertions passing and one WinError 32 fixture
cleanup error; only that sharing violation is retried briefly, with persistent
cleanup failure still raised.
