# ADR-026: Explicit original Workforce objectives and recorded progress

Status: API/migration foundation and native readonly profile implemented;
manager authoring/cancellation/recovery remains open.

A signed institute manager declares an objective's employee, title, measure,
positive target, first and last included civil days, explicit currency or no
currency, reason and original key. The supported source-grounded measures are
gross performer-attributed internally closed invoice revenue in CHF/EUR and
completed sessions with an actual finishing instant. Unknown measures are
rejected; neither planned ends nor cashier identities become performance facts.

The institute calendar resolves the configured days once. The original stores
the declared zone and half-open UTC period. Replaying a matching key returns
the original before consulting current calendar settings. Subsequent zone
changes cannot move an existing objective or its sources. An empty skipped-day
period is refused. Dates outside the supported calendar fail explicitly.

Targets are canonical decimal text, parsed and compared as Decimal. A dedicated
SQLite test proved Numeric storage changed 90071992547409.93 to
90071992547409.94. Text preserves the exact declaration and replay on SQLite and
PostgreSQL. Domain validation enforces positive bounded decimal targets and
integer session targets; database checks also enforce positive periods/targets
and metric/unit combinations. Existing invoice amounts and ledgers are unchanged.
Float and boolean targets are rejected before coercion; redundant fractional
zeros are removed without rounding. Civil days require YYYY-MM-DD dates,
not numeric epochs or datetime inputs. The 20-digit/two-decimal bound permits
at most 18 integer digits, within PostgreSQL BIGINT; the upper integer target
is explicitly tested.

Originals and separate signed cancellations retain actor, reason, key and
recording instant. Changed actor/conditions or a second cancellation are
rejected. Corrections declare a new original. Composite owner constraints link
employees and cancellations to their own institute. No update/delete route
overwrites original targets or cancellation history.

One institute lock covers source count, stable bounded objective page and
progress. Two batched aggregate queries serve the page regardless of objective
count. The recorded-revenue predicate is shared with the employee revenue read.
Invoice sources must be internally paid, retained, attributed to the employee,
within the pinned period and no later than the explicit reading instant.
Other known currencies are counted separately and never converted. Missing
matching-currency amounts or unknown units leave progress and achievement
unknown while exposing the known subtotal and diagnostic counts.

Session progress counts only completed records with an actual end within the
period, at/before the reading instant and not before their recorded start.
Planned, missing-end, invalid-interval and future-end facts do not acquire an
inferred completion. Upcoming/active/ended period states describe the read
instant; they do not predict an outcome. A cancelled original has no newly
calculated progress or source counts, rather than fabricated zero performance.

Migration 6ade31b9204f creates only the objective/cancellation tables and scoped
index/constraints. Empty roundtrips are supported. Offline downgrade and removal
of any original/cancelled history are refused before DDL. Owned SQLite and
PostgreSQL fixtures verify metadata parity and preserved facts. Application
databases are not migrated by these checks.

The native readonly employee profile reads objectives independently of the
selected calendar day and shows each original civil period, pinned zone,
exact target, current source progress, unknown diagnostics and cancellation.
BigInt cents preserve exact comparisons and redundant-zero replay equivalence.
Response validation checks ownership, complete bounded pages, pinned DST/skipped
day boundaries, source counts, period state and achievement at generated_at.
Cancelled facts require null progress/counts. Fresh failed reads hide old facts;
employee and signed-session changes isolate late responses. Original identifiers,
actors/reasons and UTC bounds remain in a 44px provenance disclosure. Direct
profile navigation avoids scrolling through long calendar histories.

Native manager authoring/recovery and physical/production acceptance remain
open. Objectives do not define payroll, commissions,
external settlement, refund attribution, net revenue or workforce hours. Those
remaining Employee 360 authorities stay separate in WORKFORCE_GATE_AUDIT.md.
