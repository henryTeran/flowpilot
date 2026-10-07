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

## 12H: native manager customer directory and observed profile

`frontend/src/components/CustomerCrmPanel.tsx` binds the existing registered
customer search (maximum 20 results, explicit selection) to the guarded current
segment read. Manager navigation uses the existing Clientes entry and a lazy
bundle. Institute/token/customer changes dispose old reads; query changes clear
choices and selected profiles. Refresh immediately hides previous facts, and
malformed/failed responses show an actionable reread instead of old classification.
Reception makes no sensitive CRM request through this panel.

Profiles show the observed state or precise unavailable/unknown explanation,
ticket count, last closing, known gross by currency, rounded-to-cent recorded
average basket, missing amount/currency/date diagnostics, and expandable period
and original policy provenance. Large money formatting uses BigInt and the
display-only average rounds half up explicitly; source ratios remain unchanged.
The directory does not create a default policy or expose policy mutations yet.

Native browser evidence revealed the existing CustomerRead creation timestamp
lost UTC metadata on SQLite. `backend/app/modules/customers/schemas.py` now uses
AwareDatetime with the established stored-UTC restoration helper, preserving
actual creation instant rather than accepting naive timestamps. Existing customer
identity/search/checkout behavior is preserved and a UTC JSON assertion added.

Controlled evidence: initial focused profile/segment tests 5 passed in 4.18s;
final complete frontend 238 passed in 42.43s, zero failures/skips. TypeScript/Vite
build passes, 115 modules, separately loaded CRM bundle about 10.42kB. Backend
customer/checkout/profile focus 9 passed in 20.23s; final customer/checkout focus
after the explicit UTC assertion 5 passed in 9.59s; existing passlib crypt warning
only. Signed Edge desktop/touch-tablet 2 passed in 33.9s (6.7s/4.6s), real isolated
customer and explicit policy, native search/selection/current profile, corrupted
classification hidden then recovered, all controls at least 44px and no horizontal
overflow. Tablet screenshot inspected. Initial Edge cases timed out on absent
search choices because naive timestamps were correctly refused; the DTO authority
was corrected without extending timeouts or weakening guards. Only launcher's
owned temporary fixture was removed, confirmed on completion. No physical-device,
actual application migration, settlement or production readiness claim.

## 12I: native explicit policy declaration/correction and recovery

`frontend/src/components/CrmPolicyPanel.tsx` integrates manager configuration in
the customer directory. Initial fields are blank, with no commercial defaults.
An explicit prepare action pins the current predecessor; correction copies the
verified original terms exactly into seconds with six decimal places. Operators
can choose days/hours/seconds, declare ordered recency/count thresholds, explicit
CHF/EUR VIP gross and a reason. Conversion uses integer arithmetic, preserving
microseconds and cents without Number rounding; unsafe or invalid values cannot
be submitted. Changing the duration unit clears durations rather than reinterpreting
old numbers. Failed/currently unread configuration or a changed predecessor blocks
new declarations rather than silently rebasing an edit.

An institute/signed-subject envelope persists before any possible POST. Original-key
GET allows POST only on explicit null. Full receipt actor/terms/key/predecessor and
an independent original reread, then a fresh selected-policy read, must verify
before clearing storage. Lost replies/remounts retain the request; failed rereads,
changed actors and invalid saved data cannot issue a duplicate write or discard
the original. Refresh remains available during recovery. Only a definitive rejected
POST permits explicit correction/discard. Successful verification refreshes any
selected customer profile. Original policy history stays in the backend correction
chain; no native delete or implicit fallback is introduced.

Controlled evidence: four initial component/conversion tests pass in 2.79s. Full
frontend 242 passed in 38.83s, zero failures/skips; after the profile-refresh hook,
final focused policy/profile tests 6 passed in 3.49s and TypeScript/Vite build passes
(116 modules, lazy CRM about 17.73kB). Tests include committed recovery with a failed
selected read, lost POST/remount/1us forged reread, late actor/invalid saved data,
exact duration/overflow handling and successful-only profile refresh callback.
Final signed Edge policy-write and customer-profile regression: 4 passed in 39.9s,
zero failures/skips, desktop/touch-tablet. Real owned initial declaration/correction
commits before its reply is aborted; reload recovery uses exactly one POST, clears
only verified storage, independently rereads matching original terms/predecessor/
reason, and preserves customer search/profile forgery rejection. Form and completed
controls are >=44px with no horizontal overflow; tablet form screenshot inspected.
Initial write-browser selectors wrongly used exact wrapped-select labels; corrected
to accessible combobox roles without extending timeouts. Launcher confirms removal
only of its owned temporary fixture. No new backend/schema or application migration,
physical-device, external message or production-ready claim.

## 12J: recorded completed-care return-cycle contract

`backend/app/modules/crm/return_cycle.py` defines explicit owned completed-care
facts with session/appointment source identity, ticket/service links, actual start,
actual completion and capture instants. Sources require a positive actual execution,
same customer/institute/capture and unique (kind, ID). Cohort membership is completion
inside the positive half-open observed window; care may start before the window.
Grouping uses only a shared explicit ticket ID, spanning its observed completed
care and retaining service IDs/counts. Nearby dates, names or phones never merge
different tickets. Ordering is deterministic by actual start/end/ticket.

The metric is the gap between successive recorded ticket-care episodes, measured
from the prior observed completion to the next actual start. Nonnegative gaps,
including zero, retain exact microseconds. Negative gaps mark overlapping episodes
and suppress the overall mean rather than averaging only the favorable subset.
Empty/single-episode cohorts have no inferred mean. Known gap sum/count and exact
string numerator/denominator remain available. These are observed source intervals,
not certified physical visits or proof of a booking/conversion; complete history
and inferred booking credit remain false. Existing explicit Workforce booking
attribution remains a separate authority.

Controlled pure CRM focus: 48 passed in 1.75s across return-cycle, billing-metric
and segmentation tests, zero failures/skips; existing passlib crypt warning only.
Nine return-cycle cases cover shared multi-care tickets, appointments/session
identity namespaces, deterministic input order, exact fractional/zero means,
empty/single/overlapping episodes, half-open bounds, scope/capture/duplicate refusal
and nonactual/naive/future source clocks. This unit has no database capture, API,
native UI, new PostgreSQL source-read or complete rebooking gate acceptance yet.

## 12K: signed actual-care return-source read

`backend/app/modules/crm/return_sources.py` and signed manager
`GET /api/v1/crm/institutes/{institute_id}/customers/{customer_id}/return-cycle`
capture actual completed session/appointment sources under the institute lock,
after registered owned-customer validation. Required aware ISO `start`/`end`
define a positive observed half-open completion period ending no later than the
server capture. Sessions link through their explicit representative ticket line
to the owned customer ticket; appointments require their explicit customer and
checkout-ticket linkage. Source performers must belong to the institute and
session service must match its representative line. Scheduled/noncompleted or
out-of-period dated records are not return evidence. Neither paid timestamps nor
customer names/phones replace actual execution dates or identity links.

A single column UNION query streams both source families in batches of 100,
with three SQL statements total (lock, registered identity, cohort). Full source
metrics are computed before slicing episodes to the requested page (default 20,
maximum 50); companion gaps follow their next episode and retain off-page predecessor
IDs. Page offsets do not truncate counts/sums/means. Known but unlinked appointments,
wrong owner/service/performer and undated/future/incoherent actual execution clocks
have explicit diagnostics; any such uncertainty suppresses the mean rather than
guessing periods or averaging the valid subset. Unknown legacy sessions lacking
a client-identifying ticket-line link cannot be attributed to this customer.
Execution/service coverage therefore explicitly stays false: session service IDs
are representative, not a claim of every care line. Complete history and inferred
booking credit remain false.

Controlled focus plus adjacent CRM regression: 61 passed in 22.36s across source/
cycle/billing/profile/metric/segment tests, zero failures/skips, actual PostgreSQL
enabled; existing passlib crypt warning only. Final source focus after explicit
coverage flags: 4 passed in 7.49s. SQLite/PostgreSQL fixtures prove 107 executions
grouped into 106 episodes across a streaming boundary, exact global mean with
20/6-row pages, three-query budget, equivalent UTC-offset bounds, undated/future
clocks, missing/wrong-client checkout links, foreign performer and foreign/opaque
registration rejection. Signed HTTP scope/period/page limits are tested. Actual
PostgreSQL pauses the whole-cohort query and proves a cooperating writer waits
until capture finishes; old/new source totals independently verified. No schema,
native UI/browser, physical-device, production or complete rebooking gate claim.

## Phase 12L: exact return-cycle frontend guards

Typed frontend guards bind the registered customer/institute and explicit aware
observation bounds to the return read. Capture chronology, incomplete execution/
service coverage, whole-cohort count conservation, canonical exact duration sums
and ratios, and all three diagnostic categories are checked before consumption.
Any diagnostic or overlapping pair requires an indeterminate mean. Positive gaps
between chronologically ordered episodes are disjoint; their total cannot exceed
the observation duration, including on partial pages.

Visible episodes independently validate actual positive clocks, completion cohort
membership, unique ticket/service links and execution counts. Adjacent visible
gaps are recalculated with integer microseconds. Complete pages reconcile global
counts/sums; partial pages check their contributions and predecessor identity
without pretending to know off-page actual clocks. Empty/single cohorts retain no
mean, complete customer history and inferred booking credit remain false.

Controlled full frontend regression: 245 passed in 38.56s, zero failures/skips.
Final focused guards after the stricter partial-page sum bound: 3 passed in 0.84s;
TypeScript/Vite build passes (116 modules). Scope, offset aliases, forged ratios/
counts/gaps, duplicate links, boundary completion dates, diagnostic/overlap
uncertainty, empty and partial pages and impossible hidden totals are covered.
Guards are not yet native-bound; existing bundles remain unchanged. No backend,
new browser, physical-device or production receipt is claimed. Canonical CRM
gates remain open.

## Phase 12M: native recorded-care return profile

The native manager profile binds return-cycle reads to the verified policy's
observed start/end. Without a usable segment period, it does not guess care
windows. Customer/institute/token/period changes dispose previous requests;
refresh and page transitions hide stale facts. Care capture time is displayed
separately from payment capture time, preserving their distinct observations.

The profile displays complete-cohort episode/execution and gap counts, uncertain
diagnostics, and the exact mean rendered with integer half-up rounding to
hundredths of days. Incomplete execution/service/history coverage and absence
of inferred booking credit are explicit. Twenty-row episode pages show actual
clocks/ticket provenance and companion off-page predecessor IDs while retaining
global metrics. Empty/overlapping/damaged cohorts do not produce a fabricated
mean. Long source identifiers wrap on tablet.

Controlled frontend focus: 7 passed in 3.21s; complete frontend regression:
247 passed in 48.76s, zero failures/skips. TypeScript/Vite build passes, 118
modules, lazy CRM approximately 24.08kB. Role/customer/actor stale responses,
forged means, empty uncertain history, integer display rounding and 20/1-row
pages with 21 global episodes are tested. Signed Edge policy/profile regression:
4 passed in 1.1m, desktop/touch tablet, zero failures/skips. Each real profile
fixture creates two completed sessions through signed ticket/start/finish APIs,
verifies ticket provenance/known gap, hides forged means and recovers fresh
facts. Existing profile and committed-policy recovery still pass. Controls are
at least 44px with no horizontal overflow; tablet screenshot inspected. Owned
fixture cleanup confirmed. Existing bcrypt/NO_COLOR warnings only. No new
backend/schema, actual application migration, physical-device or production
receipt is claimed; all four CRM gates remain open.

## Phase 12N: explicit remaining-lifetime value calculation

`backend/app/modules/crm/lifetime.py` defines an explicit, scoped conditional
remaining-lifetime scenario. Required declarations are model version, currency,
expected active microseconds, activity fraction, gross contribution margin and
future relationship costs. Activity/margin fractions are canonical bounded
integer-string ratios between zero and one; durations/costs are canonical
bounded strings. There are no inferred commercial defaults.

The undiscounted model is explicitly:

- projected gross = selected-currency observed gross / observed microseconds
  × declared active microseconds × declared activity fraction;
- projected contribution = projected gross × declared gross contribution margin;
- remaining CLV = projected contribution − declared future relationship costs.

This is a remaining-value scenario conditional on declared assumptions, not
historical gross relabelled as CLV, a complete historical net value, a calibrated
prediction or guaranteed lifetime. Margin/costs remain declared assumptions,
not inferred from paid tickets. CHF/EUR never combine or undergo invented FX.
The result retains its source billing and every assumption/diagnostic. Existing
`billing.predicted_clv` remains null; complete history, validated prediction and
discounting remain false.

Integer/Fraction arithmetic produces reduced signed integer-string ratios with
no intermediate floats, silent cent rounding or loss of negative/zero results.
Explicit zero gross/activity can yield zero contribution and negative remaining
value after costs. Empty history is unknown. Stale observations, undated/future
closings, calendar overflow, unknown currency, no observations in the selected
currency or uncertain selected-currency amounts suppress all monetary outputs.
UTC elapsed-time arithmetic preserves offset aliases.

Controlled pure lifetime/metrics/segments regression: 62 passed in 0.52s, zero
failures/skips, including 23 new lifetime cases. Initial 61 passed in 0.65s
before final timezone/calendar case. Exact negative/fractional/zero arithmetic,
large costs above safe JSON integer precision, strict required assumptions,
scope/diagnostics, uncertainty priority, separate currencies and calendar bounds
are covered. Existing Starlette/httpx deprecation warning only. No original
storage, API/UI, actual PostgreSQL, migration, broader regression, physical-device
or production receipt is claimed. Native original declaration/recovery and
authoritative billing/diagnostic reads remain required; CRM gates stay open.

## Remaining acceptance

- Extend customer profile/source views for remaining lifecycle metrics and events
  without changing complete aggregates or guessing name/phone identity. Native
  policy configuration/recovery is delivered; no production policy is configured
  by controlled browser fixtures and no lifecycle event is claimed yet.
- Implement source-supported CLV semantics and complete canonical rebooking
  acceptance, distinguishing recorded gross from prediction and employee credit.
  Native observed return-cycle reads are delivered; this does not certify visits,
  complete customer history or close the whole rebooking gate.
- Implement explicit birthday/communication declarations and lifecycle events
  for birthday, post-service, rebooking, inactivity, package expiry and
  subscription renewal; verify scope, provenance, repeatability and cancellation
  behavior. Actual external messages have not been sent or authorized here.
- Integrate and test native customer profile/workflows on desktop and tablet;
  close functional gates only with executable evidence. Physical-device and
  production readiness gates remain separate and open.
