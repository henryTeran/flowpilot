# Phase 12 CRM acceptance evidence

Canonical authority: Master Plan section 33. All four CRM phase gates remain
OPEN: CRM_SEGMENTS, REBOOKING, CUSTOMER_LIFECYCLE, AUTOMATION_EVENTS.

## 12A: exact recorded billing metric foundation

`backend/app/modules/crm/metrics.py` defines immutable, explicit scoped facts
and a pure cohort calculation. A caller must supply an entire observed cohort,
not a page of tickets. Every fact must match institute, registered customer
identity and capture instant, have a unique ticket ID, and close inside the
positive half-open observation window ending no later than capture.

Results distinguish recorded ticket frequency from physical visit frequency.
Recency is the exact capture-to-last-recorded-closing interval in microseconds;
an empty cohort has no last closing or recency. Counts per microsecond and
average baskets are exact integer ratios, avoiding float rounding. Known gross
amounts sum independently by CHF/EUR. Missing/invalid amounts suppress that
currency cohort's average rather than becoming zero. Unknown currencies count
separately and mark currency classification incomplete. Explicit zero remains
valid. No FX conversion, complete-history claim or predicted CLV is inferred.

Controlled evidence: `backend/tests/test_crm_metrics_12a.py`, 16 passing tests
on local SQLite-configured test infrastructure (the calculation itself is pure),
0.38s. Existing Starlette/httpx deprecation warning only. Tests cover empty
history, exact fractional average, mixed currencies and missing/invalid gross,
canonical amount validation, source scope/capture, duplicate identities,
half-open boundaries, offset-equivalent instants and exact microsecond windows.
No PostgreSQL, API, native UI or production acceptance is claimed by this unit.

## 12B: retained registered-customer billing read

`backend/app/modules/crm/billing.py` locks the institute before verifying a
registered owned customer and capturing the server clock. It streams selected
paid-ticket columns in batches of 100 across the whole requested observed
window, with three SQL statements (lock, identity, cohort). There is no line
join or pagination-based aggregate truncation: the basket source is the retained
ticket total, including quantities and invoice corrections once. Queries convert
aware bounds to UTC before binding, including on SQLite. Tickets outside the
window, from another institute/customer, unpaid or with unknown closing times
cannot contribute. Historical opaque references never establish a CRM identity.
The resulting complete-cohort calculation still does not establish complete
customer history, physical visits or external settlement.

`GET /api/v1/customers/institutes/{institute_id}/{customer_id}/billing` requires
the signed own-institute manager; existing reception customer search/create/detail
remain unchanged. Required `start` and `end` are explicit aware ISO instants,
with a positive half-open window ending no later than server capture. Invalid
periods return 400, missing query parameters 422, unavailable registered customer
404, and disallowed role/institute 403. Amount diagnostics preserve missing versus
invalid retained gross; exact Decimal coefficient arithmetic avoids ambient
rounding and rejects floats, negatives, fractional cents and source overflow.

Evidence: `backend/tests/test_crm_billing_12b.py` includes SQLite and actual
PostgreSQL complete-cohort reads (109 eligible tickets across a batch boundary),
three-query budget, offset-equivalent bounds, identical name/phone identities,
foreign owned customer/ticket scopes, missing/invalid gross, signed HTTP access,
invalid periods and source arithmetic. Actual PostgreSQL concurrency pauses the
reader after the institute lock and proves a cooperating writer cannot commit
until the reader finishes; old/new totals are independently verified. Combined
CRM and existing customer identity/checkout regression: 26 passed in 26.04s,
zero failures/skips with the PostgreSQL fixture enabled; existing passlib crypt
deprecation warning only. Final run includes the UTC-alias correction.
No new migration, native browser/UI or production acceptance is implied.

## 12C: explicit observed segmentation contract

`backend/app/modules/crm/segments.py` adds an immutable policy contract with no
commercial defaults: observed horizon, recent-registration age, risk/dormant
recency thresholds, loyal/VIP ticket-count thresholds, and a VIP gross threshold
in one explicit CHF/EUR currency. Strict positive integer thresholds refuse
coercion. Risk precedes dormant and both lie inside the horizon; VIP count exceeds
loyal count. These are observed retained-billing segments, not inferred physical
attendance or complete historical labels.

Classification requires an owned registered customer, the exact declared horizon,
and an explicit undated-paid-ticket diagnostic. A historical period not ending at
capture or any undated closing produces an indeterminate result (`state: null`)
with a precise reason. With no observed closing, recent registration can establish
NEW; an older registration remains indeterminate rather than becoming DORMANT.
For dated activity the precedence is DORMANT, AT_RISK, VIP, LOYAL, ACTIVE. Recency
boundaries are inclusive at risk/dormant thresholds, to the microsecond. VIP
requires the explicit ticket count and currency gross thresholds, without FX.
Known gross is a valid nonnegative lower bound even with missing amounts; if it
cannot prove VIP and missing amounts/currencies could change the decision, the
result stays indeterminate. Otherwise the known count supports LOYAL or ACTIVE.
Result pins policy, registration fact, metrics and diagnostics for explanation.

Controlled evidence: all three CRM test files pass, 43 tests in 11.60s, zero
failures/skips with actual PostgreSQL enabled; existing passlib crypt warning
only. The 22 segmentation cases cover all six states, exact recency/registration/
gross boundaries, inactivity precedence, missing/unknown evidence, known-gross
lower bounds, same-currency versus foreign-currency spend, stale/horizon/scope/
future-registration refusal and strict ordered thresholds. No policy persistence,
segment API, native UI or production acceptance is delivered by this contract.

## 12D: signed policy originals and explicit correction chain

`backend/app/modules/crm/models.py`, `policies.py` and `routes.py` persist
explicit policy terms, signed actor, reason, server recording instant and original
idempotency key. An institute-scoped current pointer selects the policy without
guessing from timestamps or random IDs. The initial declaration requires explicit
`previous_policy_id: null`; a correction requires the exact current original ID.
The institute lock and fresh pointer read serialize concurrent corrections.
Every correction appends an original and moves the pointer atomically, retaining
its predecessor and terms. No delete, in-place term change or implicit fallback
to an earlier policy is exposed.

Original-key replay verifies the same actor and all submitted terms before
mutable pointer/clock checks. A committed declaration can therefore be recovered
after another correction or a backward clock without issuing a new policy. New
corrections refuse a clock earlier than the predecessor. Responses preserve aware
UTC instants on SQLite. An absent configuration remains explicit null, without
creating a default policy.

Signed own-institute managers use `/api/v1/crm/institutes/{institute_id}` with
POST `/segment-policies` and GET `/segment-policies/current`,
`/segment-policies/original/{key}`, `/segment-policies/{identifier}`.
The declaration body contains the complete explicit `policy`, required predecessor,
reason and idempotency key; caller-supplied actor/recording metadata are refused.
Foreign policy scope and stale predecessors are refused, and receipts are scoped.

Migration `b72d4e91a603` follows `ac61f9d028e5`. Composite foreign keys enforce
same-institute predecessor and current-pointer ownership; unique institute/key
and institute/ID constraints retain replay identity. Online downgrade refuses any
recorded policy/pointer history; empty-schema round trips remain supported. Models
are registered in runtime and Alembic metadata. Existing migration acceptance
tests update only their expected latest head, preserving their original history
guards and assertions. No actual application database has been migrated.

Combined all-CRM and affected SQLite/PostgreSQL migration regression: 67 passed
in 162.30s (2m42), zero failures/skips, actual PostgreSQL enabled; existing
passlib crypt warning only. Policy tests prove retained originals, correction,
same-actor replay after pointer/clock change, stale/foreign/unsigned refusal,
signed HTTP access and actual concurrent corrections accepting exactly one
writer. Both-database migration tests verify composite ownership, empty round
trip, protected recorded history and metadata parity. Initial focused HTTP
fixture had a mismatched signed actor; its refusal was correct, the fixture was
aligned and the final combined run passes. This unit does not implement segment
reads, native configuration UI, production thresholds or automation delivery.

## 12E: scoped current-policy segment snapshot

`backend/app/modules/crm/profile.py` and
`GET /api/v1/crm/institutes/{institute_id}/customers/{customer_id}/segment`
bind the signed own-institute manager to a registered owned customer. A single
institute-locked transaction reads the fresh selected policy original, captures
one server instant, counts owned paid tickets with undated/future closing times,
and streams the entire current-horizon billing cohort using the existing exact
capture authority. No client clock, chosen historical period or alternate policy
can replace this current selection. Normal configured reads use six SQL statements
independent of ticket count; the prior explicit-period billing read still uses
three statements after factoring out its shared capture.

The response retains customer registration, complete selected original provenance,
capture instant, undated/future counts and observed segment explanation. Absent or
future policy, future registration/closings, and an unrepresentable calendar horizon
produce an explicit unavailable reason with no invented segment or fallback.
Undated closings preserve available recorded metrics but keep classification
indeterminate through the existing classifier. Diagnostics cannot be assigned a
guessed period: undated counts cover owned paid records, not an inferred date.
Complete customer history remains false.

Controlled all-CRM regression: six test files, 52 passed in 31.57s, zero
failures/skips, actual PostgreSQL enabled; existing passlib crypt warning only.
New SQLite/PostgreSQL integration covers absent/current/corrected/future policy,
registration and source diagnostics, exact six-query budget, 109-ticket full
cohort, original pins, server-derived horizon, unknown currency/gross, invalid
calendar extent and foreign/opaque identities. Signed HTTP tests cover roles and
tenant scope. Actual PostgreSQL concurrency pauses the reader at source diagnosis,
proves a correction writer waits, then verifies old-policy VIP and subsequent
corrected-policy indeterminate results independently. Initial fixtures inherited
microsecond recency thresholds despite hour-old tickets; their correct DORMANT
results exposed the fixture inconsistency. Explicit hour-based test thresholds
were supplied without changing production classification, then all tests passed.
No new schema migration, native browser/UI or production acceptance is claimed.

## 12F: exact frontend recorded-billing guards

`frontend/src/crm-billing-utils.ts` validates customer/institute scope, requested
window aliases and exact aware microsecond chronology before rendering recorded
billing. It independently verifies ticket/currency/amount-quality count
conservation, unknown-currency completeness, canonical nonnegative gross strings
bounded by known source count, frequency and average-basket ratios, recency and
empty-history semantics. CHF/EUR groups must be unique and ordered. Missing or
invalid gross cannot become a zero average; complete-history and predicted-CLV
substitutions are rejected. Unsafe JSON numeric counts are refused rather than
rounded. Monetary sums beyond JavaScript's safe numeric range use BigInt.

The backend `ExactRatio` now serializes **both numerator and denominator as
canonical integer strings**, with a strictly positive denominator. This corrects
the experimental CRM response contract before native consumption: very long
observed periods have microsecond denominators beyond JSON/JavaScript numeric
precision. No existing native CRM consumer is bound to the previous numeric
denominator; repository usage was inspected. The frontend verifies the exact
ratio against clock/count arithmetic without passing denominators through Number.

Controlled frontend regression: 231 passed in 48.22s, zero failures/skips;
TypeScript/Vite production build passes (111 modules; existing main/Workforce
bundles unchanged, guard not bound to UI yet). Four new test groups cover scope,
UTC-offset equivalents versus 1us changes, forged ratios/counts/source bounds,
missing/invalid/unknown and empty history, noncanonical money, unsafe counts and numeric denominators,
large exact aggregates and a year-1 observation period. Backend CRM regression
and long-horizon JSON serialization: all six CRM files, 53 passed in 124.72s
(2m04), zero failures/skips with actual PostgreSQL enabled; existing passlib
crypt deprecation warning only. No schema or persisted source change is required.
No native profile, policy-receipt/segment guard or signed-browser acceptance is
claimed by this billing foundation.

## 12G: frontend policy original and current-segment guards

`frontend/src/crm-policy-utils.ts` validates explicit owned policy terms, ordered
thresholds, canonical gross and safe JSON integer fields, original ID/predecessor,
signed actor and aware recording metadata. Receipt matching pins every declared
term, actor, reason, predecessor and key. Original comparison preserves identity
and semantic microsecond instants, accepting equivalent offsets and refusing a
1us change. Numeric policy fields that cannot be represented exactly by JavaScript
are refused rather than rounded; no threshold is invented to repair a response.

`frontend/src/crm-segment-utils.ts` binds customer registration, selected original
policy, server capture, source diagnostics and the existing exact billing guard.
It derives the current observation horizon and independently recomputes the
classification and reason, including count/gross lower bounds, currency ambiguity
and inactivity precedence. It checks unavailable-reason precedence for absent or
future policy, future registration/closings and calendar underflow, preserving null
segments. Policy/customer/clock/diagnostic substitutions and complete-history
claims cannot become visible profile facts.

Controlled evidence: five new test groups; final full frontend regression 236
passed in 54.79s, zero failures/skips. TypeScript/Vite production build passes
(111 modules; existing main/Workforce bundles unchanged, guards not UI-bound).
Tests cover scoped strict policies, ordered/unreachable/coerced thresholds,
receipt actor/key/predecessor/terms, offset aliases versus microsecond mutations,
profile substitutions, exact unavailable reasons, undated sources, all six states
and exact risk/dormant boundaries, and representable-policy calendar underflow.
Backend contracts/schema are unchanged; existing 12F backend receipt remains
53 passing CRM tests, without claiming a new backend or browser run.

## Remaining acceptance

- Integrate the delivered signed billing read into native customer profiles;
  add any bounded source-history views without changing complete aggregate
  coverage or inferring identity from name/phone.
- Integrate delivered current-horizon segmentation and diagnostics into native
  configuration/profile workflows, including guarded original-key recovery and
  explicit absent/future policy presentation. No production threshold is configured
  by 12E, and no lifecycle transition/event is claimed yet.
- Implement source-supported CLV and customer rebooking-cycle semantics,
  distinguishing recorded gross from prediction and employee rebooking credit.
- Implement explicit birthday/communication declarations and lifecycle events
  for birthday, post-service, rebooking, inactivity, package expiry and
  subscription renewal; verify scope, provenance, repeatability and cancellation
  behavior. Actual external messages have not been sent or authorized here.
- Integrate and test native customer profile/workflows on desktop and tablet;
  close functional gates only with executable evidence. Physical-device and
  production readiness gates remain separate and open.
