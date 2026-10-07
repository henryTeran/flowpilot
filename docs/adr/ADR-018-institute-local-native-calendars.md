# ADR-018 — Institute-local native calendars

Status: accepted; 151 frontend and 30 signed backend Edge cases pass.
Final focused native refinement: four resource/repeated-hour cases pass with
production rebuild and owned cleanup; final tablet screenshot visually reviewed.

## Reproduced problem and decision

Phase 10T corrected API civil-day bounds. Appointment authoring/editing and the
planning display still derived their dates/hours from the workstation. A Los
Angeles workstation could therefore present and submit a different civil clock
from a Geneva institute. Native visual review also exposed the same dependency
in the availability detail beside the planning board.

The existing institute timezone is now explicit in App, AppointmentPanel and
PlanningBoard. Invalid/missing legacy zones use the existing explicit UTC
fallback. Appointment dates, clock labels, search, initial rounded slot and edit
fields use the institute zone. Institute wall time resolves to zero, one or two
actual UTC instants. A skipped/invalid time cannot POST; a repeated time requires
an explicit first/second occurrence. A default or original existing instant may
retain its known occurrence. Merely editing other fields preserves the original
start string, including its seconds and microseconds; changing the civil slot or
occurrence submits the newly selected instant. Existing replay keys survive a
failed request within the same unchanged form. Institute/timezone/auth remounts
discard old local form state.

The planning axis uses elapsed instants between institute civil boundaries, not
workstation hours or civil-minute subtraction. Spring's missing hour is omitted;
autumn's repeated ticks show their UTC offsets. Both occurrences have distinct
positions, and a service spanning a clock change retains its real duration and
positive width. Cross-midnight intervals are clipped to the displayed institute
window. A skipped display boundary advances to its first existing instant; this
display rule never resolves an appointment mutation implicitly. The next-day
midnight endpoint is labeled 24:00. Naive appointment/session instants are not
silently interpreted using the workstation. Bounded explicit-zone formatter
reuse and one shared window per board avoid recalculating boundaries per row.

The existing 09:00–20:00 display and out-of-hours demo adaptation remain display
conventions. They do not establish institute working hours, employee attendance,
leave policy or scheduling eligibility. Those official decisions remain in the
deterministic Flow & Capacity Engine.

## Verified UX correction and scope

Native repeated-hour testing reproduced a second issue: editable fields during
an outstanding booking/operational refresh allowed the next client name to be
entered and then erased by completion of the previous request. Authoring fields
are now disabled until that operation finishes; concurrent appointment actions
and authoring are guarded. Touch controls in the authoring fieldset and the
conditional occurrence selector have a minimum height of 44px.

Utility/component checks cover three workstation zones, midnight clipping,
both Zurich transitions, Lord Howe's half-hour transition, original timestamp
precision, explicit occurrence selection and pending-operation protection.
Native signed backend tests cover creation/movement/resource conflict/retry on
Los Angeles workstations and two future repeated-hour bookings separated by one
real hour, verified using the signed explicit-day API. The latter is native
authoring plus API read verification; it does not establish native browsing of
arbitrary future days. The agenda still receives the operational today's list.
An independent selected-day agenda read is the next correction, without changing
the current-day inputs of the live planning/capacity board.

No backend, migration, stock fact, monetary rule, certificate or absence model
changes. Physical tablet, production performance/clock drift, workforce and
production readiness acceptance remain open. Final counts and committed scope
are recorded in PROJECT_STATUS.md.
