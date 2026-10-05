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

Safe movement/modification, customer reservation and complete hybrid
booking gate validation remain open. Moves must atomically revalidate qualifications,
employee/walk-in conflicts and resource intervals under the institute lock.
