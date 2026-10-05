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

Booking integration and live resource projections are not yet implemented. Live
assignment options and estimates still report configured resource needs as unknown;
booking writes still fail closed. Phase 5B must connect these reads and booking
lifecycle, and prove resource-specific PostgreSQL races before resource gates pass.

Evidence: `test_resources_skills_5a.py` exercises roles, tenants, configuration replay,
all-line qualification checks, reservation guards and unknown resource capacity.
`test_resources_migration_5a.py` checks SQLite and opt-in PostgreSQL round-trips and
metadata parity. `test_postgres_qualifications_5a.py` races assignment against skill
removal in independent PostgreSQL transactions. These checks do not establish load
performance or real browser/tablet usability.
