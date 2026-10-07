# ADR-017 — Scoped source indexes and atomic SQLite migrations

Status: accepted for Phase 10T; full PostgreSQL-enabled regression verified.

## Problem and decision

The Phase 10Q/R readers filter operational sources by institute, status and
actual completion or scheduled slot. Separate single-column indexes do not
provide the same scoped range access. Migration `2c897df4e6fb`, following
`1b786cf3d5ea`, adds compound appointment completion/slot, session completion and
queue status indexes. Models and migrated schemas declare the same indexes.
The migration only changes indexes; it rewrites no source, norm, stock, order,
receipt or invoice facts. Removing just those indexes is safe with populated data.

The existing populated purchase-history migration guard reproduced a SQLite
schema defect after the new revision: a deeper blocked downgrade retained the
purchase facts but removed all four new indexes while metadata still expected
them. PostgreSQL already rolled the DDL back. SQLite's migration engine now
disables driver-owned legacy BEGIN and emits BEGIN through SQLAlchemy's begin
event, with transactional DDL enabled for the entire Alembic chain. A later guard
failure therefore restores indexes and Alembic version as well as data.

This transaction control applies only to the engine created in Alembic's online
environment. Runtime application engines and PostgreSQL transaction/locking
boundaries are unchanged. The technique follows
[SQLAlchemy's SQLite transaction documentation](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#enabling-non-legacy-sqlite-transactional-modes-with-the-sqlite3-or-aiosqlite-driver).

## Verification and deployment boundary

The first full PostgreSQL-enabled regression reached 484 passing cases and
one failure in the live two-process action test. Its last appointment was two
hours ahead, in the institute's current civil day but the next UTC day. Agenda
reads used UTC midnight and omitted it. Agenda and day-planning readers now use
the institute's half-open civil-day bounds converted to UTC; DST days therefore
span 23 or 25 hours. Planning retains overdue active sessions independently of
their day and excludes completed sessions merely touching a day boundary.
Invalid legacy zone names use the existing UI's UTC fallback. No stored instant
is changed. The backend explicitly requires `tzdata` so Windows/fresh installs
do not depend on an incidental database-driver dependency for IANA zones. The
Windows calendar checks use the installed package; the Linux checks also cover
the system timezone database. Agenda GET additionally accepts an optional explicit civil `day`
date, keeping signed institute/role checks and the default local-today behavior.
The live test reads its future booking's explicit institute date, so it also
remains valid when the two-hour horizon crosses local midnight.

Six focused calendar/live cases pass, including both DST transitions, local
midnight, half-open edges, overdue active visibility, explicit-date authorization
and the actual PostgreSQL two-process action scenario. Calendar-extreme date
inputs return a controlled business error instead of overflowing the datetime
range. This fixes a reproduced regression; it does not add workforce hours,
attendance facts or historical timestamp corrections.

Nine focused cases pass: populated index roundtrips on SQLite/PostgreSQL,
deeper blocked downgrade with exact fact/schema/version preservation, prior
inventory/supplier/purchase migration guards and a default PostgreSQL query plan
on 6,000 historical appointments using the scoped actual-completion index.
No sequential-scan setting is disabled to force that plan. This is a concrete
index-eligibility/workload check, not a production latency or concurrency SLO.

Four signed backend Edge booking/resource and walk-in lifecycle cases also pass
on desktop and touch-enabled tablet-landscape, with a production build and owned
fixture cleanup. These profiles use the institute zone; appointment authoring
and planning-axis workstation-zone independence remain a separate UI correction.
Full PostgreSQL-enabled backend regression: 489 passed, no failures or skips
in 1004.24 seconds. Existing passlib crypt and legacy SQLite datetime-adapter
deprecation warnings remain. Four fresh calendar cases on each of Windows and Linux cover the final
extreme-date guard after the full suite was collected. All migration databases are
owned temporary files or random test schemas. No existing application or
production database is migrated. Production index-build duration, write locking,
backup/restore and deployment acceptance remain open. The regular transactional
index migration is not a zero-downtime index rollout.
