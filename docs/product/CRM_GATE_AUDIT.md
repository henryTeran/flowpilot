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

## Remaining acceptance

- Integrate the delivered signed billing read into native customer profiles;
  add any bounded source-history views without changing complete aggregate
  coverage or inferring identity from name/phone.
- Persist signed explicit lifecycle policies and their original/correction
  provenance; capture undated paid-ticket diagnostics and current policy horizons
  under the shared lock, then expose the delivered segmentation through scoped
  reads and native profiles. No production policy or threshold is configured by
  12C, and no persisted lifecycle transition/event is claimed yet.
- Implement source-supported CLV and customer rebooking-cycle semantics,
  distinguishing recorded gross from prediction and employee rebooking credit.
- Implement explicit birthday/communication declarations and lifecycle events
  for birthday, post-service, rebooking, inactivity, package expiry and
  subscription renewal; verify scope, provenance, repeatability and cancellation
  behavior. Actual external messages have not been sent or authorized here.
- Integrate and test native customer profile/workflows on desktop and tablet;
  close functional gates only with executable evidence. Physical-device and
  production readiness gates remain separate and open.
