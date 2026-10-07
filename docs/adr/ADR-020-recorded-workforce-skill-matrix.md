# ADR-020 — Recorded workforce skill matrix

Status: accepted; 157 frontend cases and 25 focused backend cases pass,
including actual PostgreSQL serialization. Broad signed Edge regression passes
32 cases. Final matrix/reception checks after sidebar refinement pass four cases
with production build and owned cleanup; the tablet screenshot was reviewed.
Final full PostgreSQL-enabled backend regression passes all 493 cases without
skips or failures; existing dependency/legacy timestamp-adapter warnings remain.

## Decision

Canonical Master Plan section 32 requires a Skill Matrix within Workforce.
The existing resource engine already owns employee skills and institute-specific
service requirements. Workforce must project those authorities rather than
introduce a parallel qualification or availability engine.

`GET /api/v1/workforce/institutes/{institute_id}/skill-matrix` requires an actual
signed reception or institute-manager token with that exact institute. Missing
institutes return 404; absent, foreign and disallowed-role credentials return
403. This endpoint performs no configuration mutation. Its active global service
catalog axis uses the institute's own requirements; its employee axis includes
all recorded institute employees, independently of today's availability.

Each axis has its own offset and limit (default 10, maximum 25). Rows are ordered
by identity, total counts are explicit, and each returned employee/service pair
has one cell. A request contains at most 625 cells. Selected employees use the
same union of legacy JSON and structured skills as resource matching; selected
services use the same recorded requirements. Optional identity filters on the
existing fact readers bound these reads without changing their unfiltered
scheduling/resource callers. Query count is at most eight, including institute
lock, axis counts and data reads; there is no query per cell.

The bounded read acquires the existing institute row lock used by employee,
skill and requirement writes. This avoids combining pre-replacement legacy
skills with post-replacement structured skills under PostgreSQL's existing
transaction configuration. The request dependency closes its session and
releases the read transaction. A real two-session PostgreSQL test pauses after
the legacy query, proves the writer remains blocked, then verifies the original
matrix and the replacement matrix separately. This choice trades a short
serialized read for consistency; production contention, timeouts and service
level acceptance remain unproven.

Cells expose `meets_recorded_requirements` and exact missing codes. A service
without recorded requirements carries `none_recorded`. Its empty-set match is
consistent with the existing engine, but the UI says "Aucune exigence
enregistrée" rather than implying certification. Coverage never establishes
resource capacity, employee presence, a bookable interval, or a certification.

## Native read

The Équipe navigation opens a standalone matrix with independent employee and
service pagination (10 by 5). It reads directly from the signed matrix endpoint,
not the live board's employee page. Institute/auth changes remount the read;
disposed, superseded and old-token replies cannot publish. Loading, rejection
and malformed responses hide old facts. Validation checks page metadata,
identities, complete cell coverage, required/missing codes, booleans and scope.

Recorded requirements, missing codes and unconfigured requirements have
distinct text labels. The bounded table supports contained horizontal scrolling
and keyboard focus; the refresh/pagination controls are at least 44px. Read time
uses the institute zone. The expanded sidebar scrolls within its own height so
lower navigation items remain reachable above the logout control.

## Evidence and remaining scope

Tests cover signed HTTP roles/tenant boundaries, exact union matching,
unconfigured requirements, absent employees, inactive service exclusion, full
axis traversal, constant query count and actual PostgreSQL read/write ordering.
Frontend tests cover contradictory/incomplete/foreign matrices, both pagination
axes, readonly reception, failed refresh/retry, institute/token changes and
disposal. Edge exercises the real protected configuration APIs followed by
native refreshed reads, corrupts one returned coverage flag to test fail-closed
display, and refuses a foreign scoped request. Fixture configuration is restored;
all databases are owned disposable fixtures.

This delivers the recorded Skill Matrix. It does not finish Employee 360,
certification/expiry, native skill authoring, scheduled absence/leave, objectives,
recorded work hours, commissions or the rest of Workforce. No schema migration
or existing application database change is involved. Physical tablet and
production gates remain open. See WORKFORCE_GATE_AUDIT.md for section 32 mapping.
