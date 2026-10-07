# ADR-025: Employee-attributed internally closed revenue

Status: API foundation verified; native profile integration remains open.

Employee 360 reads existing ticket/line invoice facts without a new monetary
ledger. The employee scope requires the recorded performed_by_employee_id on
each line. A cashier, checkout operator or creator is never substituted for a
missing performer. The institute-wide number of internally closed unattributed
lines is explicit context, not revenue assigned to the selected employee.

The selected civil day is the institute day containing paid_at, with existing
half-open UTC boundaries and DST/skipped-day behavior. Only internally paid
tickets and retained invoice lines are included. Unpaid tickets, removed invoice
lines and the exact next-day boundary are excluded. Original line ID, ticket ID,
service ID, category, quantity, amount and ticket currency remain visible rather
than recomputed from the current catalogue or guessed from invoice operators.

The institute lock covers exact source count, currency aggregation and stable
bounded paging. Decimal amounts serialize as strings. Each recorded currency
has its own group; a missing amount leaves the full total unknown while the
known subtotal is separately labelled. Unknown-currency lines have no aggregate
amount. Counts remain available where a monetary total cannot be asserted.

This is gross recorded line attribution on internally closed invoices. It does
not assert external settlement, net revenue or allocation of a ticket-wide
refund to a performer. It is distinct from legacy commercial cashier fallback
reporting: the employee profile must name the attribution basis explicitly.
Native reading will preserve these distinctions and exact money strings.

Canonical section 32 requests certification facts and a Skill Matrix. A new
service credential matching policy is not an explicit additional gate. Existing
configured skill requirements remain authoritative; optional future credential
rules require explicit configuration instead of inferred grants. Remaining
Employee 360 fields and physical/production acceptance stay open.
