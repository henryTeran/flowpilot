# ADR-009: Currency-scoped service reporting

Status: accepted for internal reporting; production validation remains open.

## Problem

Legacy Chiffres summed paid performed-line amounts across all historical ticket
currencies and exposed a single unlabelled total. CHF, EUR and missing historical
units cannot establish one comparable monetary value. Current institute settings
cannot relabel an original paid invoice.

## Decision

Use the immutable paid ticket currency to partition Chiffres into CHF/EUR groups.
Each group retains employee attribution, revenue categories, distinct ticket counts,
performed-service counts and its own per-ticket average. The source paid-ticket set
and UTC reporting period are shared across groups. Decimal accumulation uses an
explicit precision of 28, independent of the caller's decimal context. Known comparable monetary values remain Decimal through the DTO and serialize as
plain two-decimal strings, including zero. There is no intermediate float cast.

The summary includes `currency`, `currency_groups` and `unknown_currency_tickets`.
Its legacy monetary fields are decimal strings only for one known currency with no unknown
paid tickets. Mixed or unknown units return null for those fields, not zero or a
cross-unit sum. Nonmonetary counts remain available. Missing historical currencies
are counted separately and excluded from monetary grouping: missing units cannot
be assumed equal to one another. No FX conversion, current-settings fallback or
paid history mutation is introduced. No database migration is required.

The UI selects one currency group at a time and labels it. Unavailable amounts use
an em dash. Historical unknown-unit exclusions are visible; old unlabelled payloads
cannot display monetary values without a known unit. Consumers must accept nullable decimal-string
monetary fields. The UI groups digits and renders the recorded fractional text directly,
without converting the monetary value to a JavaScript Number. Cashflow, fees, taxes, refunds and bank settlement remain
separate from gross performed-service reporting.

## Validation

SQLite and PostgreSQL fixtures verify CHF/EUR/unknown historical separation,
unchanged scoped access, single-unit totals, distinct counts and arithmetic under a
caller decimal precision of 2. Frontend tests verify switching groups without
showing the other unit's total and suppressing unlabelled legacy totals. Existing
checkout regressions are retained. The two-process live protocol fixture explicitly
configures invoice currency before asserting comparable revenue. Browser/tablet
visual verification and complete accounting remain open.


The precision regression includes 90071992547409.93, whose cent value exceeds
JavaScript's safe integer range. Both API serialization and display must preserve
.93 exactly. Known currency groups and unknown-unit suppression are unchanged;
original paid invoice facts are not rewritten. Prior full-suite evidence remains a
baseline; final focused report/checkout and live two-process protocol checks cover
this serialization change.
