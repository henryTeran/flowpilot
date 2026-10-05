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
The core is not yet connected to database reservations or official scheduling writes.

Resource allocation integration is not yet implemented. Configured resource requirements make
capacity unknown and block assignment, start and booking. A catalog entry alone does
not prove availability. Phase 5B must provide reservations, lifecycle release,
extension collision handling and joint projections before resource gates can pass.

Evidence: `test_resources_skills_5a.py` exercises roles, tenants, configuration replay,
all-line qualification checks, reservation guards and unknown resource capacity.
`test_resources_migration_5a.py` checks SQLite and opt-in PostgreSQL round-trips and
metadata parity. `test_postgres_qualifications_5a.py` races assignment against skill
removal in independent PostgreSQL transactions. These checks do not establish load
performance or real browser/tablet usability.
