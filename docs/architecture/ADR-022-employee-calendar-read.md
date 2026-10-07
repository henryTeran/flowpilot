# ADR-022: Employee profile and day calendar foundations

Status: Accepted at controlled API/component/Edge scope.

The manager-only individual profile reads current employee identity and the
existing authoritative skill union. Current availability comes from the existing
availability engine at one explicit generated_at instant. Selecting another
calendar date does not turn that current reading into a prediction.

The selected day uses the institute calendar's half-open UTC bounds. Sources are
scoped to both institute and employee before a SQL union of appointments,
executions and original absence intervals. Overlapping overnight intervals are
included. A skipped civil day has an empty interval and no events; 23/25-hour days
retain their elapsed UTC boundaries. Active executions without a recorded end
remain visible even after their planned end, without inventing a finishing time.

Appointments retain booked boundaries separately from explicit actual start/end
facts. Session planned ends are not actual finishing times. Planned-only sessions
do not acquire an inferred actual start. Original absence cancellations remain
visible as cancelled history. Service names are current catalogue labels; source
IDs and recorded intervals identify the underlying facts.

The shared institute lock serializes source counting, bounded paging, skill reads
and current availability with operational writes. Pages have an exact total and
stable start/kind/identity ordering, with a maximum of 100 events. This is a
read-only view: no schema or operational status changes. Actual PostgreSQL tests
pause between count and page and prove a competing absence writer waits; the
original page is coherent and the next transaction sees the newly recorded fact.

Native employee/date selection masks stale facts, verifies response scope and
complete page coverage, and ignores late old-token responses. Explicit institute
formatting includes UTC offsets so repeated hours remain distinguishable.
Controlled Edge checks use an LA host clock and desktop/touch-enabled tablet
profiles. Signed disposable fixture APIs create/finish an execution and prepare
future booking/absence facts for native read verification; this is not a claim of
physical execution or native business authoring in that specific calendar test.

This delivers availability, skills and calendar foundations for Employee 360.
Certifications, objectives, exact attributed revenue, occupancy, rebooking,
configured commissions and recorded workforce hours remain required. Planned
durations are never treated as attendance or an occupancy denominator. Phase 11,
physical-device and production acceptance remain open.
