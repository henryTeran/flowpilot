# ADR-021: Original workforce absence intervals

Status: Accepted at controlled migration/API/component/Edge scope.

Scheduled absence and leave are operational unavailability facts. They do not
establish leave entitlement, medical categories, attendance or payroll approval.
An institute manager records an employee, explicit UTC interval, kind and reason.
The server derives institute ownership and actor from the signed route context.
Naive timestamps and body-supplied actors are rejected.

The original interval is immutable. Cancellation is a separate signed fact,
retaining its own reason, actor and idempotency key. Original-key recovery returns
the original interval with its cancellation, including after its start time.
Reusing a key with changed terms or actor is refused. Cancelled intervals release
capacity without erasing history. Composite foreign keys enforce employee and
cancellation ownership; unique constraints enforce replay and single cancellation.

The existing institute lock serializes interval creation with appointment,
assignment and actual-start mutations. Creation rejects overlapping original
active intervals, committed appointments, executions and assigned queue duration.
Overdue executions have unknown remaining duration and prevent scheduling an
absence until resolved. Actual starts, appointment moves, queue assignments and
session extensions independently refuse active absence overlap. Half-open
intervals permit work ending exactly at an absence start or starting at its end.

Availability and queue projection feed these intervals into the existing free
window engine. No second scheduler or automatic Employee.status mutation is
introduced. Current planning presents recorded absence separately from the
employee's manual status. Operational availability exposes a blocker identity,
without the manager-only reason or leave details.

Migration 3da908e5f70c adds the original and cancellation tables and employee owner
index. Empty downgrade is reversible. Any recorded history, including cancelled
intervals, refuses downgrade before DDL. Tests run in disposable SQLite databases
and random PostgreSQL schemas; no application database is migrated.

The native manager section authors institute-clock civil dates and requires an
explicit occurrence for repeated hours. Missing local hours never generate an
instant. Requests are stored per institute and signed actor before transport.
Recovery reads the original key first; a missing original permits replaying the
same terms, while a recorded original is verified without another POST. Original
identity, actor, interval and terms plus fresh absence and operational planning
reads are required before clearing storage. Late old-token replies cannot submit
a POST or clear a different session's request. Separate motivated cancellation
uses the same recovery lifecycle. Reception has no sensitive absence panel/read.

Controlled desktop/tablet browser acceptance covers original creation and
cancellation after lost replies/reload and repeated institute hours on a host in
another timezone. The native view is paginated interval history. An employee
calendar, Employee 360 and physical/production acceptance remain open; it does
not close the entire Phase 11 ABSENCES gate.
