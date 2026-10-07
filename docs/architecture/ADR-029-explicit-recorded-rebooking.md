# ADR-029: Explicit recorded employee rebooking

Status: original declaration/cancellation API and migration implemented;
bounded employee declaration-day read and profile component implemented;
readonly profile verified on controlled Edge; native lifecycle and acceptance remain open.

Bounded manager source/target choice APIs support native authoring without raw
ID entry. Source choices use actual completion day (explicitly distinct from the
declaration-day journal) and include completed sessions/appointments with known
ending instants in shared half-open institute bounds. Missing-start/incoherent,
future-ending, unknown-client and already-attributed choices retain explicit
disabled reasons. Completely unlocated completion never borrows a planned end;
`complete_sources=false` retains unknown coverage. Owned line/ticket and client
relations are joined/correlated in the bounded read; eligible rows return their
typed actual capture. Separate cancellation releases active source eligibility.

Target choices revalidate the selected execution under the institute lock and
page current active appointments for that exact owned client. They never infer a
client from a name or phone. Joined creation-event counts reject missing or
duplicate original provenance; active existing target attribution disables reuse.
Past/legacy choices are visible with disabled reasons instead of fabricated
creation dates. Eligible target capture uses the same pure booking validation
as signed writes, preserving original and current booked slots and exact event
chronology. Events are grouped only for that client's scoped current candidates,
and rows do not trigger per-option source queries. Selection remains a snapshot:
the signed original write revalidates authoritative facts and active uniqueness
before creating any declaration. No source/target choice creates attribution.

Native choice guards independently verify exact scoped source captures and
completion-day eligibility, including backend exclusion priority. Target choices
must match the selected execution/client, one creation event and positive
original/current slot chronology with exact microsecond comparisons. Drift in
source, client or current captured slot cannot silently become the selected
request; invalid/attributed choices must have null capture. Choice guards allow
the target's assigned employee to differ from the original performer, preserving
execution attribution. Controlled guard tests/build pass; the selector/form and
signed native lifecycle remain pending.

The reusable selector component now pages validated actual-completion choices
and then same-client target choices, displaying disabled reasons rather than
entering raw IDs. Scope/token remounts and current source/page/revision guards
isolate late responses. Source refresh withdraws both captures immediately;
target replies from that previous source revision cannot repopulate them. Fresh
read failures hide choices and withdraw the parent selection; disabled recovery
does not initiate choice reads. Civil clocks/offsets aid selection and exact
captured instants remain in disclosures. Component tests/build pass; live
Workforce form routing, signed request recovery and Edge selector acceptance
remain pending.

Canonical section 32 requires employee rebooking; section 33 separately requires
CRM rebooking cycles and automation. Neither defines an employee attribution
window or permits guessing customer identity. Employee rebooking will therefore
record an explicit signed link from an actual completed execution to a later
booking for the same explicitly linked institute customer. A chronological
coincidence does not create that link automatically. This preserves the existing
booking engine and does not introduce another scheduler or send CRM messages.

The input capture validates completed walk-in sessions through their owned
ticket-line/ticket customer link, or completed appointments through their
explicit customer ID. Actual positive start/end instants must have finished by
the shared capture clock; planned ends never substitute for missing execution.
The recorded performer supplies employee attribution, never booking creator or
cashier. Employee and customer must belong to the institute. Names, phones and
free-text notes are not returned or compared.

A target must be an existing active booking for that same customer. Exactly one
owned `created` BookingEvent supplies its creation instant and original slot;
missing or ambiguous legacy provenance is rejected rather than reconstructed
from today's planned slot. Creation must occur at or after actual completion
and by the capture clock. Original slot starts after creation, and the current
recorded booked slot remains after completion. Cancellation/no-show, self-link,
changed customer, malformed/naive snapshot clocks and contradictory intervals
are refused. Current rescheduling may change the slot: both the original
creation slot and current booked slot are captured distinctly.

The source customer link is observed at declaration time, not claimed as an
immutable historical completion snapshot where no such snapshot exists.
The original fact pins validated source/customer/performer,
execution instants, target/event/creation instants, both slots, signed actor,
reason, idempotency key and recording instant under the institute lock. Replay
must return the original before evaluating later source/booking/clock changes.
Separate motivated cancellation must preserve the original; active source and
target attribution must be unique to avoid crediting one booking repeatedly.
Fresh bounded history and original-key reads are available; native lost-reply
recovery remains required.

Manager-only scoped writes serialize on the existing institute transaction lock.
New declarations validate captured sources, then refuse either a source or target
already linked by a non-cancelled original. Separate cancellation releases that
attribution for an explicitly corrected declaration while retaining all history.
Same-key replay validates exact requested source/target/reason and actor before
consulting current source, booking or clock state. Cancellation similarly
replays its original signed terms before considering current cancellation state.
The bounded employee history counts and pages under one institute lock, with a
single outer join for cancellation; it does not fetch sources per original.

Migration 8af04d719b32 follows 72c18fba901d. Composite ownership foreign keys
protect employee, actual session/source appointment, target and cancellation.
SQL enforces exactly one source kind and rejects appointment self-linking.
Pinned captures are JSON containing typed instants/IDs, never customer names or
phones. Any original/cancelled history blocks downgrade before destructive DDL;
offline downgrade cannot bypass history verification. No existing application
database is migrated by the controlled tests.

Employee 360 will label counts as recorded declared rebookings and retain
original provenance plus subsequent target cancellation/no-show diagnostics.
An absent declaration is unknown attribution, not a failed rebooking. No full
conversion rate, causal employee performance or future attended-return claim
is inferred from incomplete declarations. CRM cycles and automated reminders
remain separate canonical work.

The manager employee day endpoint explicitly uses `declaration_recorded_at`:
the institute civil day of the original recording instant, not execution day,
booking creation day or planned return day. It retains shared half-open calendar
bounds, timezone and one capture clock under the institute lock. Exact global
counts partition all originals into cancelled declaration, future recording,
unknown target, cancelled booking, no-show, booked return and completed return.
Cancelled declarations retain their provenance and take precedence; future
recordings are explicit after clock regression. Changed/missing current client
links cannot support a known return. Booked returns are reservations, not a
prediction of attendance. A completed return requires the same explicit client,
positive actual endpoints ending by the snapshot clock and actual start after
the pinned source completion and at/after original booking creation. Planned
slots never fill missing actual endpoints.

Both current actual endpoints and client/status facts are returned beside the
unchanged original so native guards can verify the classification. Counts cover
all originals through bounded 100-row streaming; the stable history page is
independently limited and uses joined facts without per-source queries. Snapshot
counts/page are protected against institute writers; the subsequent reading
includes writes committed after that snapshot. `complete_attribution=false`
and null conversion basis points retain unknown full conversion, including an
empty journal. This read adds no schema or write path.

The selected-day manager profile now uses exact BigInt response guards for
pinned source/booking chronology, microsecond instants, employee ownership,
original/cancellation identities and declaration-day bounds. Current target
classification is independently recomputed against that same capture clock.
Exact count keys conserve the whole journal; complete pages reproduce counts,
partial pages require visible counts not to exceed global counts. Duplicate
active source/target credits on a visible page are refused while cancelled
history remains readable. Original recovery comparisons include every pinned
instant and client/service/event identity without float conversion.

The component displays read timestamp, explicitly recorded-day counts and
unknown complete conversion, with original provenance in a 44px disclosure.
Primary execution/creation instants use institute civil time and UTC offsets;
exact originals remain in provenance. Empty journals do not imply rebooking
failure. Fresh failures hide previous facts; day/employee/token remounts isolate
late replies and reception initiates no reads. Controlled component tests and
production build pass. Backend-connected signed workflows and Edge desktop/tablet
verify explicit customer-linked execution/booking/declaration provenance, corrupt
fresh-read refusal/retry, original preservation after target cancellation,
employee switch to empty unknown attribution, direct navigation, 44px controls
and horizontal fit. Final tablet provenance screenshot is inspected. Native
authoring/cancellation/lost-reply recovery and physical/production acceptance
remain required; no actual future attendance is claimed.

Controlled SQLite and real PostgreSQL source tests verify both execution kinds,
exact microsecond chronology, explicit identity, original creation provenance,
invalid/missing/future execution, target states, malformed clocks, foreign
scope and duplicate creation events. Original lifecycle tests additionally verify
actor/term conflicts, correction, replay after changed booking and regressed
clock, separate cancellation and PostgreSQL competing attribution/same-key
writers. Migration tests verify metadata parity, empty roundtrip, named ownership
and source constraints, and intact retained history. Production and physical
acceptance remain open.
