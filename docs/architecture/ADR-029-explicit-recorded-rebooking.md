# ADR-029: Explicit recorded employee rebooking

Status: original declaration/cancellation API and migration implemented;
native lifecycle, Employee 360 day read and acceptance remain open.

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

Controlled SQLite and real PostgreSQL source tests verify both execution kinds,
exact microsecond chronology, explicit identity, original creation provenance,
invalid/missing/future execution, target states, malformed clocks, foreign
scope and duplicate creation events. Original lifecycle tests additionally verify
actor/term conflicts, correction, replay after changed booking and regressed
clock, separate cancellation and PostgreSQL competing attribution/same-key
writers. Migration tests verify metadata parity, empty roundtrip, named ownership
and source constraints, and intact retained history. Production and physical
acceptance remain open.
