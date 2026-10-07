# ADR-019 — Independent selected-day native agenda

Status: accepted; frontend regression passes 153 cases. Broad signed backend
Edge regression passes 30 cases. Final focused resource/repeated-hour scenarios
pass four cases after offset labels, with production build and owned cleanup.
The selected-day tablet screenshot was visually reviewed.

## Decision

The appointment drawer now reads its own selected institute civil date through
the existing signed explicit-day appointments API. The operational appointments
state in App remains the current-day input to live planning and availability.
Changing the agenda date never replaces that state or the planning day.

The date defaults to the institute's actual current date, independent of the
workstation. Creation and movement select the saved appointment's date after
the existing callback succeeds, including next-day slots near midnight. Actions
refresh the selected date. Operational refreshes also invalidate that read, so
the selected agenda follows committed real-time changes through the existing
REST resynchronization path. Mutation authorization, resource conflicts and
idempotency remain enforced by the existing signed server endpoints.

Reads are disposed on date, institute, timezone, auth remount, operational
refresh or explicit retry. A prior read cannot publish in a new scope; the
captured access token must still match before publishing. Loading, failure and
malformed responses hide cached appointment facts. Responses must be arrays
with unique identities, matching institute and selected start date, known
statuses, aware positive intervals and valid field types. The reader does not
truncate the API's daily response. Invalid dates issue no request.

The agenda has separate loading/error/retry states and a 44px date control.
Repeated institute clock hours on cards include their actual UTC offsets, so
the two occurrences remain distinguishable in the selected-day results.
All card mutation controls are disabled throughout another pending mutation,
including creation while the parent operational refresh is still completing.
The actual browser reproduced a dropped cancellation click during that period;
the disabled state now lets native automation and users wait for completion.
The existing original creation key survives failed attempts.

## Evidence and limits

Component tests cover reversed date responses, invalid/foreign snapshots,
failed reads and retry, post-action refresh, institute remount, invalid dates,
disposal and pending-write controls. The checkout workflow fixture explicitly
selects its historical booking date rather than returning it as today's fact.
Signed disposable-backend Edge tests cover current-day movement/conflict/retry
and future repeated-hour appointments, with native cancellations, switching dates without changing the operational
planning day, distinguishable UTC offsets and a 44px date control. The final
calendar-date validation does not require a local noon instant to exist.
Existing dependency warnings remain; no failures or skipped cases occurred.

This remains a day agenda, not a workforce availability calendar or statistical
forecast. No schema changes or existing application database access are needed.
Physical tablet acceptance, provider settlement and production readiness stay
open. Phase 11 workforce remains the next independent functional scope.
