# Resources and qualifications - Phase 5A

The resources module stores tenant-scoped rooms, equipment, beds, chairs and devices,
with explicit capabilities and operational status. Service requirements specify skill
codes and resource kind/capability/quantity. No category or legacy machine flag is
interpreted as an invented qualification or allocation rule.

Configuration routes live under `/api/v1/resources/institutes/{institute_id}`.
Reception may read; only the institute manager may change configuration or create
employees. Both roles must match the institute exactly. Changes record an actor and
action in the same transaction. Equivalent repeated configuration writes are no-ops.

Legacy employee skill JSON is preserved and mirrored into EmployeeSkill rows. The
migration deduplicates normalized rows without rewriting legacy values. Explicit
updates reconcile both representations. Scheduling uses tenant-owned facts only.

Qualification checks cover every service on a ticket. Assignment, direct start and
booking revalidate under the institute lock. Waiting projections consider qualified
employees only. Removing skills cannot invalidate committed tickets, active sessions
or appointments. Changing service requirements requires releasing commitments first.

The pure `allocation_domain.py` core matches distinct resources to quantity and
capability requirements across complete half-open intervals. It uses deterministic
augmenting paths, excludes inactive/unknown occupancy and searches reservation-end
boundaries for the earliest joint window. Eight unit cases validate these semantics.
The core is connected to queue assignment/start and service extension writes.

`ResourceReservation` and `reservations.py` now provide durable, institute-serialized
interval ownership by exactly one ticket or appointment. Reserve/release primitives
flush without committing so their caller can update operational state atomically.
Replay retains existing rows; failed matching leaves reservations unchanged. Ticket
and appointment owners share the same pool. Overdue unreleased reservations mark
capacity unknown until the owner is resolved. Three transaction tests cover these
behaviors; the new migration passes SQLite/PostgreSQL round-trips and schema parity.
Queue assignment reserves resources for the complete ticket duration. Starting
revalidates the interval and marks resources in use; extension retains the same
physical resources. Finish, unassignment and cancellation release ownership in the
operational transaction. Identical requirements across sequential ticket services
reuse their maximum quantity; different capabilities require distinct matching units.
Resource capability/status changes are blocked while reservations remain committed.
An HTTP lifecycle test exercises shared-room exclusion and failed-write atomicity.

Bookings now reserve from the same resource pool. Starting revalidates the full
duration from actual start and updates the interval; completion, cancellation and
no-show release reservations. Arrival and final transitions share institute locking.
The existing appointment start/end fields represent the updated execution interval;
separate original booked timestamps and booking movement remain Phase 6 work.
Three HTTP cases cover shared-room booking/walk-in conflicts and release. An actual
PostgreSQL two-worker race proves that different employees cannot book one room
concurrently. These are focused races, not load evidence.

Live assignment options use the same tenant-scoped resource timelines and interval
matcher as writes. They exclude the owning ticket's reservation, keep competitors
blocked, and restore eligibility on release. HTTP checks verify these transitions.
Waiting estimates now search joint employee/resource windows. Every candidate
resource window is rechecked against the employee's appointments; projected earlier
tickets consume the selected resources for their complete duration. Assigned tickets
retain priority and exclude only their own persisted reservation when recalculating.
If an assigned ticket cannot be projected, its existing resource commitment remains.
Missing or overdue unknown resource capacity yields no fabricated estimate. Extension
and finish update the facts used by queue/dashboard reads. Five pure cases and an
HTTP-backed lifecycle check cover contention, owner exclusion and overdue capacity.
PostgreSQL resource races now cover booking/booking, assignment/booking and
extension/booking across different employees. Each produces exactly one successful
writer and one conflict, with matching persisted session/reservation boundaries.
Injected assignment commit failure rolls back the reservation, ticket and event.
Service-specific availability now searches joint resource/employee windows too.
Remaining tenant/quantity/multi-service and window audits are needed for gate closure.

Evidence: `test_resources_skills_5a.py` exercises roles, tenants, configuration replay,
all-line qualification checks, reservation guards and unknown resource capacity.
`test_resources_migration_5a.py` checks SQLite and opt-in PostgreSQL round-trips and
metadata parity. `test_postgres_qualifications_5a.py` races assignment against skill
removal in independent PostgreSQL transactions. These checks do not establish load
performance or real browser/tablet usability.
