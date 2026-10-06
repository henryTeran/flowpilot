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
explicit precision of 28, independent of the caller's decimal context. Existing
numeric JSON serialization is retained for known comparable values.

The summary includes `currency`, `currency_groups` and `unknown_currency_tickets`.
Its legacy monetary fields are numeric only for one known currency with no unknown
paid tickets. Mixed or unknown units return null for those fields, not zero or a
cross-unit sum. Nonmonetary counts remain available. Missing historical currencies
are counted separately and excluded from monetary grouping: missing units cannot
be assumed equal to one another. No FX conversion, current-settings fallback or
paid history mutation is introduced. No database migration is required.

The UI selects one currency group at a time and labels it. Unavailable amounts use
an em dash. Historical unknown-unit exclusions are visible; old unlabelled payloads
cannot display monetary values without a known unit. Consumers must accept nullable
legacy monetary fields. Cashflow, fees, taxes, refunds and bank settlement remain
separate from gross performed-service reporting.

## Validation

SQLite and PostgreSQL fixtures verify CHF/EUR/unknown historical separation,
unchanged scoped access, single-unit totals, distinct counts and arithmetic under a
caller decimal precision of 2. Frontend tests verify switching groups without
showing the other unit's total and suppressing unlabelled legacy totals. Existing
checkout regressions are retained. The two-process live protocol fixture explicitly
configures invoice currency before asserting comparable revenue. Browser/tablet
visual verification and complete accounting remain open.
