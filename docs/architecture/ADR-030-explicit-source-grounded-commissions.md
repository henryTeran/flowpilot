# ADR-030: Explicit source-grounded recorded commissions

Status: internal source/terms/calculation contract implemented and checked on
SQLite and actual PostgreSQL. Signed original configured rules and separate
rule cancellations, source-linked accrual/cancellation ledger and recorded-day
exact read are implemented;
bounded rule-specific source choices are implemented; native manager lifecycle
and employee commission profile remain open.
This decision does not close the canonical COMMISSIONS or EMPLOYEE_360 gates.

The first supported basis is `closed_attributed_line_gross`: a retained line
of an internally closed paid ticket with a known CHF/EUR currency, known exact
nonnegative gross line total, positive quantity, known nonfuture closing instant
and an owned explicitly recorded performer. It shares the existing employee
revenue authority. No cashier, assignment, ticket name, planned execution or
external settlement is substituted. Removed invoice lines, incomplete amounts,
unknown currency/performer, foreign sources and incoherent closing chronology
cannot produce an accrual from this basis. Missing source terms stay unknown;
a known zero amount or an explicitly configured zero rate can produce zero.

The source capture stores institute, ticket/line, actual performer, service,
category, currency, quantity, full line gross minor units, arrival/closing and
capture instants. It contains no customer name, phone or guessed relationship.
The caller holds the same institute transaction lock as other original Workforce
writes. Capture scopes the ticket/line and verifies owned performer in bounded
queries. The immutable captured value survives subsequent source changes.

Every rule must explicitly provide employee, basis, currency, category, service
or explicit null for all services in the category, half-open UTC period,
integer rate from 0 through 10000 basis points and rounding choice. There is no
default rate, currency, service scope or rounding policy. One basis point is
1/10000 of the gross amount. Rates outside this gross-fraction contract require
an explicit subsequent decision rather than implicit extra compensation. The
period is selected by original ticket closing instant, not execution day or
rule creation time; exactly the start is included and exactly the end excluded.
Future original configuration must pin institute civil dates and zone once into
these UTC boundaries, preserving original terms on replay and calendar changes.

The calculation is per captured invoice line. Gross minor units already include
line quantity: it must not be multiplied a second time. Exact integer numerator
is `gross_minor * rate_basis_points`, with divisor 10000. Explicit rounding is
`half_up`, `half_even` or `down` for nonnegative results. The result retains
numerator, fractional-cent remainder, rounded minor units, full terms and full
source capture. Subsequent aggregation sums rounded line results; it must not
silently change to rounding a period-level gross sum. CHF/EUR minor units are
cents; no currency conversion, mixed-currency total or Decimal ambient-context
rounding occurs. Minor units and numerators serialize as exact strings.

Numeric(10,2) retained source amounts are checked directly from decimal digits;
floats, nonfinite/negative/out-of-source-range amounts and fractional cents are
refused. Source snapshots, terms and calculations are frozen models. UTC-aware
ISO instants are explicit; numeric timestamps and naive policy instants are
refused. SQLite's missing timezone metadata is restored only for stored domain
UTC instants, following the existing storage contract.

Next, signed original rules must retain actor/reason/key, pinned periods and
separate cancellations. Accruals must pin one original rule and one source capture,
reject duplicate active line attribution across overlapping rules, recover before
re-reading mutable authorities, and permit explicit correction only through a
separate cancellation and new original. Bounded source choices, employee reads,
native authoring and lost-reply recovery must use those authorities. No inferred
retroactive rate, commission payment, allocated refund/net revenue, payroll or
legal liability is asserted. Physical-device and production acceptance remain
separate from controlled domain/migration/API/component/browser evidence.

Original configured rules now use `employee_commission_rules` and separate
`commission_rule_cancellations`, migration `9bc52e18d430` after `8af04d719b32`.
Signed exact-institute managers supply civil first/last days, title, complete
explicit policy, reason and original key. Creation pins the institute zone and
half-open UTC period once. An empty skipped-day period or calendar overflow is
refused. The service catalog is global in the established architecture; an
optional named service must exist, while employee ownership is institute-scoped.
There are no seeded/default rules. Explicit overlapping originals are allowed;
active accrual source uniqueness under the institute transaction lock prevents
double credit instead of applying an implicit rule priority. Cancelling a rule prevents future new accruals but must not silently
rewrite or cancel existing pinned commission originals.

Matching actor/terms replay is resolved before current calendar or clock reads.
Original terms and captures remain unchanged after timezone changes or later
cancellation. Conflicting actor/terms fail. Rule cancellation has its own original
key, one cancellation per rule, signed actor/reason and independent original
receipt read. Matching cancellation replay precedes current clock validation;
a new cancellation refuses a clock earlier than the rule original. Both create
and cancel hold the shared institute transaction lock, including PostgreSQL
competing same-key writers. Cancellation never deletes a rule or edits its rate.

Manager routes expose create, original-key recovery, original-ID read, separate
cancellation and cancellation-key recovery, plus employee history with stable
period/id ordering and limit <=50. Journals join cancellations in one bounded
page query, with independently counted totals; no per-rule receipt lookup. The
`calculation_terms` adapter reads only the original pinned terms for future
source-linked calculations. Reception, other institutes and unknown employees
cannot access this rule authority.

Migration metadata matches both SQLite and PostgreSQL. Constraints retain
employee/rule ownership, optional service reference, unique replay and unique
cancellation, explicit basis/currency/rounding/category and bounded integer rate
with positive period. Empty upgrade/downgrade roundtrip is verified on owned
fixtures; any recorded rule or cancellation prevents downgrade before DDL.
Earlier protected-history migration tests remain compatible with the new head.
No existing application database is migrated by these controlled tests.

Source-linked originals now use `employee_commissions` and separate
`commission_cancellations`, migration `ac61f9d028e5` after `9bc52e18d430`.
A signed manager supplies only original rule ID, retained line ID, reason and
request key. The server derives employee/ticket/currency, captures the complete
uncancelled rule and closed-line facts once, and computes exact rounded cents.
Rules recorded after the capture clock or cancelled rules cannot create new
accruals. A matching original request resolves before current rule, source or
clock validation, preserving recovery after changes or later cancellation.

Each accrual retains full rule snapshot, typed source/terms/numerator/remainder/
rounded-result calculation, explicit derived currency/minor-unit columns and
actor/reason/key/recorded instant. DTO reads recheck rule/source/employee/ticket/
line identity, matching captured and recording clocks, original rule chronology,
exact policy and recomputed integer arithmetic, plus agreement with retained
money columns. Separate cancellation must reference the same original/institute
and cannot precede its recording instant. No live rule or invoice re-evaluation
changes an original receipt; in particular later rule cancellation does not
retract an existing commission or release its active source credit.

Before a new accrual, a joined original/cancellation read refuses any uncancelled
commission for the same owned invoice line, across every overlapping rule.
Creation and correction hold the shared institute lock. Actual PostgreSQL tests
prove competing different-rule/key requests yield precisely one active original,
while competing identical requests recover the same original. SQLite checks
cover domain/constraint behavior; they are not PostgreSQL concurrency evidence.
Only explicit commission cancellation releases source eligibility. A corrected
new original can select another eligible rule while preserving all prior facts.

Manager routes provide create, original-key/ID reads, separate cancel and its
original-key read, and bounded employee journal including retained cancellations.
Stable recorded-time/id paging counts all originals and joins cancellations in
one bounded page read, with no per-original rule/source/receipt requests. Empty
or partial journals are not evidence of complete commission entitlement. Source
choices, day/profile aggregation and native protected recovery remain required.

The migration retains composite institute/employee, institute/rule,
institute/ticket and ticket/line ownership, original/replay uniqueness,
one separate cancellation per original, and source/employee-history indexes.
Per-line minor-unit columns must be canonical nonnegative integer text within
the Numeric(10,2) source bound; no binary floating amounts are stored. Empty
roundtrip/metadata parity and actual foreign/malformed-money/duplicate-cancellation
constraint checks pass on owned SQLite and PostgreSQL fixtures. Nonempty history
refuses downgrade before any DDL. No application database is migrated or external
settlement, refund allocation, payroll or production acceptance asserted.

The employee `commission-day` manager read now selects originals by half-open
institute civil bounds on commission recording time (`commission_recorded_at`).
That cohort is explicitly distinct from source ticket closing day, rule period
or cancellation day. Current institute zone resolves the requested day once;
original pinned rule periods are not rebased. Rows retain complete original
provenance plus current separate cancellation; no mutable invoice/rule joins
rewrite the captured gross, currency, rate or result.

Global counts partition the cohort into `recorded`, `cancelled`,
`future_recording` and `future_cancellation`. An original after the captured read
clock is a future recording; otherwise an existing cancellation after that clock
is a distinct future-cancellation diagnostic. These clock diagnostics are not a
historical-state reconstruction or silently credited/payable amounts. Later known
cancellation moves the original to cancelled even if cancellation occurred on a
different day. Each state preserves its exact original minor-unit sum separately
per CHF/EUR currency. There is no mixed-currency sum, floating SUM, complete
entitlement or payment inference; `complete_entitlement=false` and
`payable_total=null`, including empty journals.

The shared institute transaction lock covers bounds, generation clock, global
aggregate and page. A bounded-memory streamed joined original/cancellation read
validates each captured authority before adding Python integer amounts; a
separate stable recorded-time/id page retains global totals across pagination.
There are no per-row source/rule/cancellation queries. Actual PostgreSQL tests
pause the aggregate after locking, observe a concurrent writer attempting its
real institute FOR UPDATE, prove it stays blocked, then verify an entirely empty
first snapshot and the new original in the next read.

Controlled SQLite/PostgreSQL cases verify mutated-source independence,
recorded/cancelled/future-original/future-cancellation states, separate currencies,
23-row 20+3 paging and exact global cancelled sums, Zurich 23/25-hour days,
skipped Apia day, real writes at exactly included start/excluded end boundaries,
unknown entitlement on empty rows and signed scope/limit/date refusals. Full
production-cohort performance and native/profile/source-choice acceptance remain
open. No schema or application database change is made by this read addition.

Manager rule-specific `sources?day=...` choices now use actual ticket closing day
in shared half-open institute civil bounds (`source_closed_day`), explicitly
separate from commission recording day. The original rule is read under the
institute transaction lock. Candidate lines are retained paid sources with the
rule's owned actual performer/category and optional explicit named-service scope;
explicit null permits all services in that category. Unknown/unlocated closing
instants, unassigned performers and removed/unpaid lines never acquire invented
clocks or cashier attribution. `complete_sources=false` preserves unknown coverage.

One independently counted, stable closing-time/ticket/line page joins source
facts and correlated active-attribution/future-cancellation checks. There are no
per-option employee, receipt, source or rule queries. Eligible previews use the
same pure `capture_values` authority and exact `calculate` function as writes;
source ownership and performer scope are established by the bounded read before
that helper is called. The original-rule snapshot and full preview terms/source/
exact calculation are included; selecting or reading a preview does not create
any commission or protect against later source changes. The final write captures
and revalidates authoritative facts again.

Visible candidates retain explicit disabled reasons: cancelled/future rule,
already attributed source, future cancellation clock, future closing instant,
unknown/mismatched currency, closing outside the original pinned period or
invalid source amounts/quantity/chronology. Invalid nonfinite/nondecimal amounts
or noninteger quantities are represented as unknown raw values without fabricated
eligible captures. All excluded previews are null. Later known cancellation
releases eligibility; a cancellation timestamp later than the capture clock
continues blocking a new source credit in both choices and final ledger writes.
Original request-key replay still precedes this new-write clock check.

Controlled SQLite and actual PostgreSQL tests verify exact preview arithmetic,
no second quantity multiplication, cross-rule attribution/correction, future
cancellation refusal before re-credit, missing/negative/nonfinite/float monetary
facts, invalid quantity/chronology, unknown/wrong currency, unlocated/unpaid/
removed/unassigned sources, named/all-service scope, source-period mismatch,
exact closing-day boundaries, future rule, cancellation, Zurich 23/25-hour and
skipped Apia days, role/institute/limit/date/missing-rule refusals and complete
27-row traversal over 20+7 with <=8 SELECTs. Ledger/day/source compatibility is
rechecked after the shared helper and cancellation-clock refinement. These
bounded API checks do not close native, complete-cohort performance, physical
or production acceptance; no schema/application database changes are made.
