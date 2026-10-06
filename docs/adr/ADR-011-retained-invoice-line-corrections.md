# ADR-011 — Retained unpaid invoice corrections

Status: accepted for the Phase 10H integration correction.

## Proven problem

On actual PostgreSQL, removing a nonrepresentative line after a multi-service
session fails with `stock_service_bases_ticket_line_id_fkey`: the existing removal
physically deletes a line referenced by the original start-time basis. The
representative line is also referenced by the session itself. SQLite without
foreign-key enforcement can conceal this defect. Refusing legitimate invoice
corrections or deleting the execution basis would change the intended workflow.

## Decision

Keep the original TicketLine, including quantity, prices, duration and performer.
Record its first unpaid invoice removal using a UTC instant, exact signed actor
and the `not_performed` reason code. This code records the existing explicit
"retirer une prestation non réalisée" action; it does not invent measured stock
quantities. All three audit fields must be absent or complete. No endpoint edits
or reverses this fact. An active institute lock serializes correction and payment.

Active invoice, payment quote, gift remainder, loyalty earning, commercial totals,
scheduling duration and resource queries exclude removed lines. New package,
member-price and reward applications reject a retained removed line. Existing
commercial-history protection and uncertain payment/tender protection remain.
Removing the last active invoice line remains refused.

The existing removal route requires exact institute scope and a bounded signed
subject. The same actor can replay the same line's original removal, including
after payment; another actor cannot replace its signature. Line identity defines
this single, irreversible-in-workflow action, so replay needs no inferred new key.
Only a new unpaid removal changes amounts. A replay never recalculates a paid
invoice or changes a newer protection.

Ticket reads return active `lines` separately from read-only `removed_lines` with
original terms and signed removal metadata. The native checkout presents removed
services as excluded from payment. Fin + caisse can still correlate a historical
representative line through that retained collection. Reloaded identification
waits for institute/planning/employee readiness before opening its modal.

Stock bases and confirmed consumptions stay unchanged. Invoice exclusion does
not establish zero physical usage, debit stock again or reverse an actual debit.
Measured consumption remains an explicit signed decision against its original
basis. This distinction preserves both billing correction and physical history.

## Migration and verification

`e84539c0a2b7` adds nullable audit fields and a paired check constraint after
`d73428bf91a6`. Existing lines retain their original terms and have no fabricated
removal. Populated signed correction history blocks downgrade before DDL. The
existing conservative populated-inventory downgrade guard is preserved so a
later migration cannot partially discard columns before a lower guard refuses.
Owned SQLite/PostgreSQL tests verify prior-schema upgrade, empty downgrade,
original terms, incomplete-fact rejection, populated refusal and model parity.
The prior inventory upgrade test seeds its actual old schema with explicit SQL
instead of applying today's ORM columns to yesterday's revision.

Actual PostgreSQL regression now accepts nonrepresentative correction, preserves
both original bases, and gives competing actors one winner. HTTP coverage checks
representative correction, signed scope, original replay after payment, last-line
refusal, unchanged actual stock and original consumption, exact quote/gift total
and corrected revenue. A focused loyalty case excludes removed prices from the
paid earning basis. Final suite and controlled Edge evidence are in
PROJECT_STATUS.md; production-provider and physical-tablet gates remain open.


Final evidence: full backend 352 passed / 81 opt-in skips before the final fresh-line
read guard; the final five correction cases pass with PostgreSQL enabled, including
that stale-read regression and the separately added loyalty case. Invoice/inventory
migration and initial correction bundle: seven passed with PostgreSQL enabled.
Frontend: 108 passed. Production build and all 18 signed backend Edge cases pass
with owned cleanup. Native recovery after a committed-but-lost removal reply and
reload preserves both bases, exposes the original actor and pays only the remaining
invoice amount. Session identity selectors correlate the actual execution despite
completed copies of the same care in the live board. The final correction block is visually reviewed on desktop/tablet with padded
readable original actor/care and invoice-versus-stock explanation. Two focused
cases pass again after the scoped layout refinement, with build and owned cleanup. Legacy queue UTC/institute-local clock display
remains a separate follow-up audit before physical acceptance.


### Phase 10I: cashier instant/display audit

Queue ticket milestones and queue events now serialize explicit instants, restoring
UTC metadata removed by SQLite while preserving aware instants and nulls. Cashier
hours use the selected institute zone instead of the workstation default. The zone
is visible; an invalid zone falls back visibly to UTC, and ambiguous input without
an offset is unavailable. No stored timestamps or billing terms are rewritten.

Twenty-four PostgreSQL-enabled timestamp/workflow/correction checks and 111 frontend
tests pass. The final build and all 20 backend-connected Edge cases pass with owned
cleanup. Native desktop/tablet browsers in America/Los_Angeles still display
Europe/Zurich cashier hours and retain explicit paid/checkout/event instants. Both
screenshots are reviewed. Other operational surfaces under foreign workstation
zones remain to be audited before physical acceptance. Original appointment invoice
line provenance and visible billing exclusion in consumption review are next;
current mutable invoice lines cannot prove historical source identity.
