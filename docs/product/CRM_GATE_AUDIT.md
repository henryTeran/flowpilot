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

## Phase 12O: lifetime original provenance and authoritative scenario API

Registered own customers now have immutable lifetime-assumption originals and
an explicit current pointer. Institute/customer/key uniqueness and composite
original predecessor/head foreign keys prevent cross-customer substitution.
The API requires signed own-institute managers and actual registered identity,
never historical opaque ticket references. Initial/corrected declarations retain
every model assumption, explicit predecessor, reason, signed actor and server
clock. Exact original-key replay returns the old receipt before mutable head/
clock checks; changed terms/actor, stale predecessor and backward clocks fail.
There are no edit/delete routes or silent rebases.

Current, original-key and original-ID routes support original recovery. The
scenario endpoint takes an explicit aware start and pins end/capture to one
server clock under the institute lock. Registered identity/date, current original,
all unknown/future-paid date diagnostics and whole billing cohort are captured
before releasing it (six SQL statements with an original). The result retains
registration and declaration provenance. No declaration, future original or
future registration returns unavailable; damaged source dates/currencies/amounts
keep projections indeterminate. Billing is streamed completely, not paginated
before calculation. The response remains a declared conditional remaining-value
scenario, not certified customer lifetime or validated predictive CLV.

Migration `c83e5fa21704` follows `b72d4e91a603`; empty downgrade/re-upgrade is
supported and online downgrade refuses recorded lifetime originals/heads. New
SQLite/PostgreSQL fixtures verify metadata equality, cross-customer pointer and
predecessor constraints and unchanged originals after protected downgrade.
Ten historical migration test files change only their expected latest head;
their existing history/schema assertions are preserved. No application database
migration was performed.

Controlled initial original/calculation focus: 26 passed in 6.43s. Adjacent CRM
original/lifetime/policy/profile/billing regression: 39 passed in 35.23s. Final
original/API focus after returning registration provenance and adding future-date
assertions: 4 passed in 20.64s, actual PostgreSQL enabled. Tests cover a complete
108-ticket cohort/constant six-query budget, exact net value, scoped receipt
replay/corrections, signed HTTP roles/owner/date and spoofed-actor rejection,
unknown/opaque customers, competing same-predecessor corrections (one succeeds),
and a real cooperating PostgreSQL writer blocked until entire capture completes
with independent before/after net values. New and ten affected migration files:
23 passed in 152.64s. All zero failures/skips; existing passlib crypt warning
only. No full-backend, new frontend/browser, physical-device or production receipt
is claimed. Exact frontend guards and native declaration/recovery/display remain
required; all canonical CRM gates stay open.

## Phase 12P: exact lifetime declaration and scenario frontend guards

Frontend contracts now validate scoped required lifetime terms, originals and
scenario reads. Duration/costs and bounded activity/margin fractions retain
canonical integer strings. Receipt matching pins every literal term, reason,
actor, key and predecessor; equivalent mathematical fractions do not silently
replace declared originals. Independent original comparison checks both shapes,
original identity and semantic aware microsecond clocks before claiming equality.

The read guard checks requested start, server end=capture, registered identity,
original scope/date and unavailable reason priority. Billing scope/window/counts/
quality and its exact ratios are verified with the existing whole-cohort guard.
Scenario assumptions must exactly match the retained original. Gross,
contribution and net remaining CLV are independently recalculated with BigInt
and greatest-common-divisor reduction; canonical reduced signed ratios preserve
zero, fractional and negative results without float conversion. The projected
active date is checked against elapsed UTC microseconds and the year-9999 bound.
Diagnostics, missing/unknown currency or uncertain amounts require null
projections with the exact source reason and correct conditional active date.
Complete history, validated prediction and discounting must remain false.

Controlled focus: 4 test groups passed in 0.89s. Complete frontend regression:
251 passed in 43.32s, zero failures/skips. TypeScript/Vite build passes, 118
modules; native bundles unchanged because lifetime guards are not UI-bound yet.
Tests cover scope/source clocks, forged/nonreduced/negative/zero/large-cost
results, declared assumption substitutions, receipt actor/literal fraction/
predecessor/clock, missing fields, registration/original date precedence and all
six source unavailability reasons. No new backend/schema, browser, physical-device
or production receipt is claimed. Native declaration/recovery/display and signed
desktop/tablet evidence remain required; all canonical CRM gates stay open.

## Phase 12Q: native lifetime original declaration and recovery

The native own-customer manager profile now exposes explicit lifetime assumptions.
Initial commercial fields are blank; prepare pins the verified current original.
Days/hours/seconds convert to exact integer-string microseconds, including values
above safe JSON integer precision. Unit changes clear the duration. Corrections
retain every original fraction numerator/denominator, duration and currency/cost
without approximate percentage conversion. Fractions are explained as retained
parts out of a positive total. Conditional constant-observed-rate, undiscounted
and nonvalidated scenario meaning is visible; there are no inferred defaults.

Requests persist before possible POST under institute/customer/signed-subject
scope. Only original-key null permits POST. Full receipt actor/terms/predecessor,
independent original reread and fresh verified current selection precede clearing
the exact persisted intent. Lost reply/remount, failed current read, wrong actor,
corrupt storage and inconsistent originals retain protected requests. Explicit
discard is limited to definitive rejected POST; refresh remains usable during
recovery. Successful-only invalidation callback is available; native scenario
display is still pending and no future monetary value is shown by this editor.

Controlled focus: 8 editor/profile/lifetime guard tests passed in 3.77s. Full
frontend regression: 253 passed in 46.58s, zero failures/skips; TypeScript/Vite
build passes, 120 modules and approximately 33.54kB lazy CRM. Tests verify one-POST
committed original recovery, failed current selection retaining intent, verified
callback/clearance, exact large duration/cost and fraction correction, wrong actor,
corrupt storage and 1us conversion. Signed Edge policy/profile/lifetime regression:
4 passed in 1.2m, desktop/touch tablet, zero failures/skips. Real lifetime initial
commit followed by aborted reply, reload/customer reselect and same-subject recovery
uses one POST. A correction pins the retained predecessor and costs; independent
current/original-ID reads verify unchanged first original. Previous policy and
profile/care forgery recovery still pass. Controls >=44px/no horizontal overflow;
tablet form screenshot inspected and owned fixture directory removal confirmed.
Existing bcrypt/NO_COLOR warnings only. No new backend/schema/application migration,
physical-device or production receipt is claimed. Native scenario display and
remaining lifecycle work are required; canonical CRM gates stay open.

## Phase 12R: native remaining-lifetime scenario display

The registered customer's manager profile now shows the guarded remaining-value
scenario beside its explicit declaration. The verified policy period supplies
start; server end/capture is fresh and visibly distinct from profile/care capture.
No usable period means no invented scenario request. Customer/institute/token/
period changes dispose old responses; refresh hides previous values. Successful
verified declaration/correction invalidates the scenario and rereads selected
original provenance. Separate requests do not pretend to be one transaction.

Gross projection, projected contribution and conditional remaining CLV are
labelled separately. Integer half-away-from-zero cent rounding is display-only;
negative values remain negative and exact signed ratios are inspectable. Original
ID/actor/reason, observation/capture, active duration/date, activity/margin fractions,
future costs and formula are visible. Unknown source conditions remain explained
unknowns; no whole-history, FX, discounted or validated prediction claim is made.

Controlled focus: 10 lifetime editor/scenario/guard/profile tests passed in 4.29s.
Full frontend regression: 255 passed in 47.81s, zero failures/skips; TypeScript/
Vite build passes, 121 modules and about 40.41kB lazy CRM. Old actor/client replies,
fresh forged net, fractional negative and large exact monetary display and no
scenario request without verified period are covered. Existing guard fixture was
extracted for reuse without changing its tests. Final signed Edge policy/profile/
lifetime regression: 4 passed in 51.4s, desktop/touch tablet, zero failures/skips.
Real signed cash payment supplies an owned closed ticket. Initial declaration and
correction refresh original provenance; no selected-currency observations remain
unknown before payment, valid scenario renders after payment, forged net hides
values and reread recovers. Existing original/policy/profile/care recovery remains
covered. All controls >=44px/no horizontal overflow; tablet scenario screenshot
inspected and owned fixture cleanup confirmed. Initial two profile cases failed
because fixture invoices lacked currency; correctly unknown scenario retained.
Owned fixture now explicitly configures CHF before ticket creation and asserts
denomination, without weakening guards/increasing timeouts. Existing bcrypt/
NO_COLOR warnings only. No new backend/schema/application migration, full-backend,
physical-device or production receipt is claimed; canonical CRM gates stay open.

## Phase 12S: explicit lifecycle declarations and birthday calendar

Source audit confirms registered customers currently have no birthday or
communication-permission authority. Existing commerce packages have issue/
expiry/balance facts; memberships have active terms and renewal originals.
`backend/app/modules/crm/lifecycle.py` adds immutable scoped declaration contracts.
Birthday is an optional evidenced month/day; a birth year is not guessed.
Exactly one explicit declaration is required per email/SMS channel and per
service-follow-up/marketing purpose. Unknown has no evidence; grants/refusals
require recorded evidence references and remain separate by purpose/channel.
Recorded permission does not itself certify a lawful/available delivery route.

Birthday observation retains explicit declaration, named timezone/leap-day
policy, registered identity/creation fact and aware capture. Scope and actual
UTC source chronology are checked, including repeated daylight-saving wall
hours. Birthday matching uses local civil date and aware midnight boundaries,
not a fixed 24-hour interval. The February-29 rule must explicitly select
February 28, March 1 or leap years only. Unknown birthday, absent anniversary
in this year, not-today and due remain distinct. Unsupported calendar bounds
fail explicitly. External delivery-authorized and message-sent flags remain
false; this pure calculation does not claim a persisted/scheduled/delivered event.

Controlled pure lifecycle/lifetime/segment/metric regression: 78 passed in 2.32s,
zero failures/skips, including 16 new lifecycle cases. Initial focus: 14 passed
in 0.69s; adjacent 77 passed in 2.22s before final repeated-hour UTC-order test.
Local-day boundaries/offsets, 23/25-hour days, all three leap policies, unknown
birthday, recorded grants/refusals, complete distinct dimensions/evidence,
strict dates/coercion, scoped registered chronology and calendar overflow are
covered. Existing passlib crypt warning only. No durable originals/calendar
policy, database capture, schema/API/UI, actual PostgreSQL source, frontend/
browser, physical-device or production receipt is claimed. Durable native
declaration/recovery and all six source-grounded repeatable lifecycle events
remain required; canonical CRM gates stay open.

## Phase 12T: durable lifecycle/calendar originals and authoritative birthday read

Own registered customers now have immutable lifecycle declaration originals and
explicit current pointers; institutes have separate birthday-calendar policy
originals/current pointers. Each original pins all declared birthday/permission
evidence or timezone/leap rule, predecessor, reason, signed actor and server date.
Same-key exact actor/terms replay returns old originals before mutable head/clock
checks. Cross-owner data, changed actor/terms, stale predecessor and backward
creation clocks fail. Corrections append and preserve past originals; no edit/
delete route or implicit calendar policy is added. Composite scoped head and
predecessor foreign keys prevent cross-client/institute substitutions.

Signed own-institute manager APIs expose declaration/calendar creation, current,
original-key and original-ID receipts. The customer lifecycle read holds the
institute lock across registered identity/creation, both current original families
and one server capture (six SQL statements when both exist). Result retains
registered source, original declaration/calendar and birthday observation
provenance. Missing declaration/calendar and future declaration/calendar/
registration remain explicit unavailable reasons; corrected unknown birthday
remains unknown. External delivery authority and sent flags stay false; this
source read is not a persisted trigger, scheduler or external message claim.

Migration `d94f6ab32815` follows `c83e5fa21704`. Four original/head tables support
empty roundtrip and online historical downgrade protection. New SQLite/PostgreSQL
fixtures prove metadata equality, cross-customer lifecycle and cross-institute
calendar pointer/predecessor refusal, retained originals and intact schema after
blocked downgrade. Eleven historical migration files change only their expected
latest head; existing downgrade targets/history checks are preserved. No actual
application database migration was performed.

Controlled initial lifecycle original/calendar/pure focus: 21 passed in 9.84s.
Final eleven CRM source/calculation/original files, excluding migration files:
112 passed in 98.76s, zero failures/skips, actual PostgreSQL enabled. Scope,
receipt replay, corrections, clock precedence, known/unknown declaration, six-
query snapshot, signed roles/HTTP/actor spoofing and both-family competing
corrections are covered. A real PostgreSQL calendar writer waits during birthday
capture; independent old/new calendar provenance verified. New plus eleven
affected historical migration files: 25 passed in 148.70s, zero failures/skips.
Existing passlib crypt warning only. No full-backend, new frontend/browser,
physical-device or production receipt is claimed. Native guard/declaration/
recovery and all six durable lifecycle event triggers remain required; canonical
CRM gates stay open.

## Phase 12U: exact lifecycle/calendar frontend original and observation guards

Frontend declaration/calendar contracts validate scoped evidenced month/day,
explicit unknown birthday, complete unique channel/purpose dimensions and
permission/evidence coherence. A valid month/day uses a leap-year reference
without inventing birth year. Calendar requires an explicit supported named
timezone and leap-day rule. Receipt/original comparators validate both shapes
before binding literal declaration evidence/permission array order, full calendar
terms, actor/key/reason/predecessor and semantic microsecond clock. A granted
permission never substitutes for another purpose or channel.

The lifecycle-read guard verifies registered source/header/capture and selected
original chronology, all five unavailable reasons in priority order, and nested
original declaration/calendar/registration/capture equality. Both outer and
observation delivery-authorized/sent flags must remain false. Declared-zone
Gregorian civil date and anniversary/leap behavior are independently derived;
bounded binary search over UTC milliseconds determines the full civil day's
boundaries. Exact microsecond comparison checks source bounds. No fixed 24-hour
day is assumed. Unsupported calendar bounds fail closed without truncating a
local day into the year range; unknown/absent birthday has null occurrence bounds.

Controlled initial terms/original focus: 3 groups passed in 0.88s. Final six
declaration/calendar/observation groups passed in 0.71s. Full frontend regression:
261 passed in 42.52s, zero failures/skips. TypeScript/Vite build passes, 121
modules; native bundles unchanged because these guards are not yet UI-bound.
Tests cover missing/duplicate/coerced/evidence facts, explicit leap birthday,
receipt actor/purpose/evidence/order/predecessor/clock, named-zone/leap declarations,
substituted source/due/date/bounds/delivery facts, UTC aliases, 23/25-hour days,
all three leap policies, not-today/unknown birthday and unavailable source priority.
No new backend/schema, browser, physical-device or production receipt is claimed.
Native declaration/recovery/observation and all six durable lifecycle event
triggers remain required; canonical CRM gates stay open.

## Phase 12V: native birthday-calendar declaration and recovery

Managers can explicitly prepare an institute calendar declaration or correction.
Initial timezone and leap-day rule remain blank. Preparation pins the verified
predecessor; correction copies the exact timezone/rule. Selected original ID,
actor, reason and human-readable leap-day behavior remain visible.

Protected intent is stored before possible POST under institute/signed-actor
scope. Original-key absence alone permits POST. Full receipt terms/actor/key/
predecessor, independent original reread and verified fresh current selection
precede clearance and profile invalidation. Lost reply/remount, failed current
read, altered original clock, wrong actor or malformed storage retain intent.
No silent rebase, guessed calendar default or unverified clearance is allowed.

Controlled calendar editor/lifecycle focus: 8 passed in 2.93s. Final full frontend
regression: 263 passed in 49.02s, zero failures/skips. Final TypeScript/Vite build
passes, 123 modules, lazy CRM 47.14kB. Signed Edge calendar/policy/customer
regression: 6 passed in 1.5m, desktop/touch tablet, zero failures/skips. Real
calendar POST commits before deliberately aborted reply; reload restores intent
and recovery uses one POST. Correction retains predecessor and independent
original-ID/current reads prove first-original preservation. Existing profile,
care, policy, lifetime/scenario and forged-read recovery remain covered.
Controls >=44px/no horizontal overflow; tablet form screenshot inspected; owned
fixture removal confirmed. Existing bcrypt/NO_COLOR warnings and nonfatal socket
reset during deliberate reply abort observed. No new backend/schema/full-backend,
application database migration, production policy or physical/production receipt
claimed. Customer lifecycle declaration/observation and all six durable event
triggers remain required; canonical CRM gates stay open.

## Phase 12W: customer lifecycle editor and guarded birthday observation

Native manager declaration/correction retains explicit known/unknown birthday,
evidenced month/day, four independent channel/purpose permission/evidence pairs
and exact original order. Protected institute/customer/actor recovery verifies
full receipt, independent original reread and current selection before clearing.
Lost reply/remount, failed current and altered original clock preserve intent.

Guarded birthday observation retains declared local calendar, UTC civil-day
bounds, selected original provenance, registered source and separate capture.
Refresh hides old facts; obsolete actor/customer responses are disposed. Fully
verified declaration invalidates observation. Unknown/absent/future facts remain
explicit; no delivery authorization, event scheduling or external message claimed.

Focused editor/observation/profile/guard regression: 11 passed in 4.13s. Full
frontend: 266 passed in 46.47s, zero failures/skips. Final TypeScript/Vite build passes, 125 modules, lazy CRM 62.11kB. No backend/schema or new backend/browser/physical/production
receipt claimed. Signed desktop/tablet lifecycle recovery/correction/observation
and visual acceptance remain required, followed by all six durable lifecycle
triggers; canonical gates stay open.

## Phase 12X: signed native lifecycle browser evidence

Signed own-customer Edge desktop/touch-tablet workflow uses a browser timezone
separate from the explicit institute fixture calendar. February-29 declaration
records granted follow-up email, refused marketing email and unknown SMS
purposes independently. Lost committed POST reply recovers after reload with one
POST. Correction to unknown birthday clears birthday evidence, retains exact
permissions and preserves independent original-ID history. Successful verified
write invalidates observation; selected calendar/declaration provenance remains
inspectable. Forged due=true for unknown birthday is refused; fresh read recovers.
French display labels replace internal rule/purpose/permission codes.

Initial selector-only failures fixed with accessible combobox role. A later
tablet independent current GET hit transient ECONNRESET after successful UI
correction; complete unchanged calendar/lifecycle/customer rerun: 6 passed in
1.1m. Final lifecycle after display-label edit: 2 passed in 37.3s. Zero
failures/skips on final runs, owned fixtures removed. Controls >=44px/no overflow;
tablet form/observation inspected. Existing bcrypt/NO_COLOR warnings and nonfatal
socket reset during deliberate abort observed. Final targeted frontend 11 passed
in 3.71s; build passes, 125 modules, lazy CRM 62.42kB. Full frontend receipt remains
266 at Phase12W. No new full frontend/backend/schema, application database
migration, external delivery or physical/production acceptance claimed.
All six durable lifecycle event triggers and canonical gate acceptance remain
required; CRM gates stay open.

## Phase 12Y: explicit six-trigger automation rules

Immutable institute policy contract requires exactly six distinct canonical rules,
each with strict enabled boolean and bounded exact integer microsecond offset.
No activation/timing defaults are supplied. Birthday has zero elapsed offset and
uses the declared civil day; rebooking/inactivity require positive intervals.
Disabled rules still retain explicit terms. Permission/delivery authority is not
inferred. Source audit distinguishes completed care, paid tickets, package balance/
expiry and membership terms/renewal originals for subsequent candidate capture.

Controlled automation-policy plus lifecycle/calendar tests: 31 passed in 0.32s,
zero failures/skips. Includes large exact microseconds, immutability, missing/
duplicate/coerced rules, invalid offset boundaries and unrequested delivery field.
Existing Starlette/httpx testclient deprecation warning observed. No durable event,
source capture, schema/API, worker, native policy editor or external delivery
claimed. Six-trigger candidates, durable rules/events, repeatability/cancellation
and worker/native acceptance remain required; canonical gates stay open.

## Phase 12Z: pure source-grounded six-trigger candidates

Typed anchors retain own-customer source identity, aware occurred/expiry clocks
and package-only strict remaining balance. Observed anchors must lie between
registration and capture; calendar birthday occurrence is explicitly distinct.
Candidates retain exact rule, policy original ID, source, due/valid-until and
capture. Post-service applies to each care episode; rebooking/inactivity use
latest observed care only, without claiming complete history. Package/membership
anticipation cannot precede source existence. Due/expiry boundaries are exact;
exhausted packages and disabled rules remain explicit. Overflow refuses timing.
Missing source yields no invented candidate; authoritative capture still needs
unavailable diagnostics. Delivery-authorized/message-sent stay false.

Controlled candidate/rule/lifecycle tests: 38 passed in 0.38s, zero failures/skips.
Covers all six candidates, source preservation, repeatable equality, latest-care
selection, missing-source absence, disabled/exhausted/expiry boundaries, foreign/
future/pre-registration/duplicate/naive/coerced facts and overflow. Existing
Starlette/httpx testclient deprecation warning observed. No database capture,
ledger/cancellation/worker, schema/API, frontend/browser or production acceptance
claimed. Durable originals, authoritative capture/diagnostics and ledger remain
required; all canonical gates stay open.

## Phase 12AA: durable automation policy originals and scoped API

Institute automation rules now have immutable originals and explicit current
pointers, scoped original/key uniqueness and composite predecessor/head foreign
keys. Signed own-institute managers can declare/read current, original-key and
original-ID. Full six-rule terms/order, signed actor, reason/key/predecessor and
server creation clock retained. Same-key exact replay precedes mutable head/clock
checks; foreign owner, stale predecessor, changed actor/terms and backward clock
fail. No edit/delete API or activation/timing defaults.

Migration ea5b7cd43926 after d94f6ab32815 adds original/head tables. Controlled
SQLite/PostgreSQL roundtrip, metadata equality, cross-institute head/predecessor
refusal and history-protected online downgrade verified. Twelve prior migration
files change only expected latest-head constants; historical targets retained.
No application database migration applied.

Initial original/rule/candidate focus: 25 passed in 6.33s. Final fourteen-file CRM
regression: 137 passed in 107.51s; new plus twelve affected migration files:
27 passed in 173.17s. Zero failures/skips, actual PostgreSQL enabled. Includes
signed roles/actor-spoof refusal, replay after clock/head changes and one-of-two
competing corrections, with prior CRM source/calculation/original regressions.
Existing passlib crypt deprecation warning observed. No new frontend/browser,
physical/production or full-backend acceptance claimed. Authoritative source
capture/diagnostics, durable event ledger/reconciliation, repeatability/cancellation
and worker/native acceptance remain required; all canonical CRM gates stay open.

## Phase 12AB: authoritative registered-customer event source capture

Signed own-institute manager read holds the shared lock across registered source,
selected automation policy, lifecycle/calendar originals, actual care and scoped
package/membership terms. One server capture is reused for birthday and all
candidates. Reusable whole care capture preserves bounded return-cycle behavior;
106 episodes are processed rather than the visible 20-row page. Complete customer
history is not asserted. Package balance/expiry and membership active terms are
validated against registration/capture; missing/invalid sources, future/absent
policy/registration, unavailable birthday and care quality stay explicit. Invalid
completed care suppresses care candidates because it can change latest completion.
Timing overflow gives no guessed candidate. Retained policy/lifecycle/calendar,
anchors/candidates and diagnostics permit subsequent reconciliation; no durable
event or delivery yet.

Initial shared care/lifecycle 9 passed in 16.43s. SQLite source fixture initially
passed catalog lists as IDs; corrected fixture, retaining guards. Focused source/
care/lifecycle/candidate regression 18 passed in 21.40s. Final fifteen-file CRM:
140 passed in 83.62s, zero failures/skips, actual PostgreSQL enabled. Covers whole
care cohort, common single clock, all six triggers with package/membership terms,
exhausted package, repeatable capture, invalid care suppression, signed roles and
foreign customer refusal. Actual PostgreSQL rule writer waits during package
source capture; old snapshot retains prior original, next read sees correction.
Existing passlib crypt deprecation warning observed. No schema/migration, ledger/
cancellation/worker, new frontend/browser or physical/production receipt claimed.
Durable reconciliation and worker/native acceptance remain required; gates stay open.

## Phase 12AC: deterministic internal-event reconciliation decisions

Logical identity retains owned scope, trigger/source kind/ID and normalized
package/membership expiry term. Policy/capture/balance/care-clock correction does
not duplicate an occurrence; renewed expiry terms are distinct. Immutable decisions
retain candidate provenance and evaluated clock, validating identity/source owner,
state/reason coherence and chronology. Repeated capture is repeatable. Disabled,
exhausted, expired and superseded terms remain distinct; newer latest care
supersedes old rebooking/inactivity. Explicit unknown birthday can cancel prior
birthday. Uncertain missing source blocks, without inventing cancellation proof.
Explicit cancellation and processed internal events are terminal.

Initial reconciliation/candidate/source 14 passed in 7.84s. Final reconciliation/
candidate/source/rule 29 passed in 8.03s, zero failures/skips, actual PostgreSQL
source capture enabled. Four new pure groups cover repetition/correction/renewed
identity, uncertain absence, terminal decisions, distinct suppression/supersession
and foreign/duplicate/backward refusal. Pure fixtures do not certify a durable
ledger; separate source tests establish selected originals/capture. Existing
passlib crypt deprecation warning observed. No ledger persistence, actual manual
cancellation/processing API, worker/schema/native/browser/full CRM/backend or
production receipt claimed. Durable scoped ledger/revisions, atomic reconciliation/
cancellation and worker/native acceptance remain required; canonical gates open.

## Phase 12AD: scoped durable event ledger schema

Capture-original table retains owner/idempotency key, actor/reason, capture clock
and full source JSON. Revision table retains event key, capture, prior revision
and decision JSON; explicit heads select current revisions. Composite capture,
predecessor and head foreign keys prevent cross-customer/event links. Schema
prepares append-only runtime behavior but does not itself certify a runtime ledger.

Migration fb6c8de54037 after ea5b7cd43926 has history-protected online downgrade.
Initial focus failed on missing explicit SQL types on generated foreign-key
columns; corrected to String(80), preserving constraints. New SQLite/PostgreSQL
roundtrip, metadata equality, cross-customer capture/predecessor/head refusal and
retained schema/history on refused downgrade verified. Thirteen prior migration
files change only expected latest head, preserving historical targets.

Final new plus thirteen affected migration files: 29 passed in 155.41s, zero
failures/skips, actual PostgreSQL enabled, exit 0. Reconciliation/source/candidate/
rule regression: 29 passed in 9.19s. Existing passlib crypt deprecation warning
observed. No application database migration, runtime append/reconciliation/
cancellation, worker, new frontend/browser or full CRM/backend/physical/production
receipt claimed. Runtime service/API, idempotency/concurrency/rollback and worker/
native acceptance remain required; all canonical gates stay open.

## Remaining acceptance

- Extend customer profile/source views for remaining lifecycle metrics and events
  without changing complete aggregates or guessing name/phone identity. Native
  policy configuration/recovery is delivered; no production policy is configured
  by controlled browser fixtures and no lifecycle event is claimed yet.
- Complete source-supported CLV and canonical rebooking acceptance, distinguishing
  recorded gross from conditional projection and employee credit. Native explicit
  remaining-lifetime declaration/recovery/scenario are delivered; calibrated or
  complete historical lifetime value has not been certified.
  Native observed return-cycle reads are delivered; this does not certify visits,
  complete customer history or close the whole rebooking gate.
- Implement explicit birthday/communication declarations and lifecycle events
  for birthday, post-service, rebooking, inactivity, package expiry and
  subscription renewal; verify scope, provenance, repeatability and cancellation
  behavior. Actual external messages have not been sent or authorized here.
- Integrate and test native customer profile/workflows on desktop and tablet;
  close functional gates only with executable evidence. Physical-device and
  production readiness gates remain separate and open.
