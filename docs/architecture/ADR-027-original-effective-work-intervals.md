# ADR-027: Original declared effective workforce hours

Status: API/migration foundation implemented; day totals, native lifecycle and
Employee 360 integration remain open.

The canonical Employee 360 requires workforce hours. Existing employee status,
appointment planning and service-session duration do not prove an employee's
effective working intervals. They cannot establish attendance or a complete
workforce-hours denominator.

A signed institute manager declares a completed effective work interval,
excluding breaks/non-working time, with employee, explicit aware start/end,
reason and original key. This is a recorded manager declaration, not a clocking
device attestation. UTC normalization preserves the actual instants, including
both occurrences of repeated civil hours. Numeric epochs, booleans, naive
instants, empty/reversed intervals and UTC overflows are refused. New effective
ends cannot be future instants. No planned end or employee status supplies a
missing effective end.

The institute lock serializes original-key recovery and overlapping declarations.
Exact actor/conditions replay returns the original before current-clock checks.
Active intervals for the same employee cannot overlap through supported API
writes; touching half-open boundaries are valid. This is an application lock
invariant, not a PostgreSQL exclusion-constraint claim. Original UTC fields
stay unchanged. A separately signed, single cancellation retains the original
and allows an explicit corrected declaration. No update/delete route erases
hours history or mutates availability, assignment or the existing scheduler.

Original and cancellation recovery reads are institute-scoped and manager-only.
The employee history uses a stable bounded count/page under the institute lock,
with cancellation facts fetched through one outer join. Composite owner FKs,
positive interval checks and institute/key uniqueness apply in the database.
Original-key races return one recorded original; different overlapping writers
produce one winner. Changing the actor or original terms is refused.

Migration 72c18fba901d follows 6ade31b9204f and adds only work-interval and
cancellation tables, scoped index and constraints. Owned SQLite/PostgreSQL
fixtures verify metadata parity, empty roundtrip and pre-DDL refusal to remove
recorded history, including cancelled originals. Application databases are not
migrated by this verification.

These records do not establish complete daily attendance, payroll, legal
working-time compliance, paid breaks or overtime. A missing record is unknown,
not proof of zero hours. Remaining work: exact institute-day clipping/duration
reads, native original creation/cancellation/lost-reply recovery, profile
integration and acceptance. Occupancy must retain explicit source coverage
and cannot infer complete working time or a ratio from an empty/partial ledger.
