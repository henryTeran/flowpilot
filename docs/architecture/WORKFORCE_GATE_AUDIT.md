# Workforce gate audit — canonical section 32

Phase 11A implements the recorded Skill Matrix. Phase 11B/C add original absence
and leave intervals with capacity protection and native manager authoring/recovery.
Controlled migration/API/component/Edge checks pass; acceptance limits remain below.
Neither unit closes Phase 11.
Phase 11D adds the employee profile/calendar foundations with current skills and
availability, bounded original interval history and separate actual instants.
Phase 11E adds original declared certifications, signed separate revocations,
explicit validity states and native manager recovery/readonly profile integration.
Phase 11F adds original signed skill changes, expected-set comparison and native
manager editing/recovery while preserving existing commitment protection.
Inventory's physical and production gates remain open while this independent
authorized Workforce scope progresses.

| Requirement | Current authoritative evidence | Remaining work |
| --- | --- | --- |
| Skill Matrix | Workforce signed scoped endpoint, native Équipe matrix, bounded independent axes, explicit missing/unconfigured requirements; `test_workforce_matrix_11a.py`, `workforce.test.tsx`, `workforce.spec.ts` | Physical-device and production acceptance |
| Compétences | Existing `Employee.skills` / `EmployeeSkill` union and `ServiceRequirement`; protected audited resource configuration and shared assignment/matrix predicate; native original-key manager changes compare the reviewed expected set and recover without overwriting later configuration | Complete workforce integration and physical/production acceptance |
| Disponibilité | Existing availability engine and live board consume recorded absences; native employee profile exposes the same current reading at an explicit timestamp independent of selected calendar day | Complete Employee 360 integration and acceptance |
| Planning | Institute-day planning plus native employee/day calendar integrates booked appointments, execution facts and original/cancelled absences; overnight, DST and skipped days retain explicit UTC boundaries | Recorded workforce shifts/hours integration and acceptance |
| Certifications | Original signed institute/employee declarations, explicit issue/end unknowns, half-open validity and immutable separate revocations; native manager lifecycle/recovery and readonly profile | Final acceptance; never infer credentials from skill codes or automatically grant a skill. New credential matching rules require explicit configuration and are optional future scope |
| Objectifs | Original signed manager targets, pinned civil/UTC periods, explicit gross-currency or actual-completed-session measure, exact targets, separate cancellations, bounded batched progress API, native manager lifecycle/lost-reply recovery and readonly employee profile | Physical/production acceptance |
| CA | Bounded manager employee/day API and native profile read performer-attributed retained internally closed lines, separate exact currencies and missing data; SQLite/PostgreSQL/component/Edge checks pass | Physical/production acceptance; no external settlement or allocated refund/net-revenue claim |
| Occupation | Native employee calendar exposes explicit actual session/appointment starts and recorded ends or missing end; planned duration is separate | Source-grounded occupancy measure; a ratio needs a known workforce hours denominator |
| Rebooking | Original execution/customer links and future appointment facts exist; no employee rebooking measure is delivered | Explicit definition and scoped recorded-event read; no inferred customer identity or predicted result |
| Commissions | No configured workforce commission ledger/rule authority is delivered | Explicit rates/basis/currency, original rule pinning, actual attributed source and protected correction/replay semantics |
| Absences | Signed manager-only original facts, capacity conflict protection, native authoring/recovery and employee calendar are verified on controlled API/component/Edge | Physical-device and production acceptance |
| Congés | Explicit `leave` intervals share the original authority, native cancellation/recovery and scoped employee/day calendar | Physical-device and production acceptance; no entitlement/payroll claim |
| Heures | Original signed completed effective-work intervals, separate cancellations, bounded manager history and native selected-day employee read; exact union durations retain DST/microseconds, excluded/overlapping sources and unknown attendance coverage | Native lifecycle/recovery and acceptance; no inferred complete attendance, payroll or legal acceptance |

Gates remain:

- `EMPLOYEE_360`: OPEN — availability/skills/calendar profile foundations delivered;
  declared certifications, attributed gross revenue and original objective lifecycle/progress added; occupation/rebooking, hours and commissions pending.
- `SKILLS`: PARTIAL — recorded matrix and existing matching/configuration are
  verified with native original skill authoring/recovery; remaining workforce and physical/production acceptance is pending.
- `ABSENCES`: PARTIAL — scheduled original facts and capacity integration are
  implemented with native lifecycle/recovery and employee calendar; final acceptance remains pending.
- `COMMISSIONS`: OPEN — configured rules and source-linked calculations pending.

Section 32 requires certification facts and a Skill Matrix. A new credential
qualification policy is not an additional canonical gate. Existing explicit
skill requirements remain authoritative; new credential rules would require
explicit configuration and must not grant skills implicitly.
Next independent unit: native hours lifecycle/recovery, then occupation/rebooking and
commissions with source-grounded authorities.
Do not create a second scheduler or derive a future absence from today's status.
Then finish the Employee 360 read/profile and explicit objective,
hours and commission authorities. Existing payment settlement and physical
tablet/production blockers do not prevent these implementations.

ADR-020 explains bounded shared-source reads and their institute-lock tradeoff.
ADR-021 explains original interval/cancellation facts and capacity arbitration.
ADR-022 explains scoped employee calendar sources, actual/planned distinction and snapshot paging.
ADR-023 explains original declared certifications, separate revocations and recovery.
ADR-024 explains original skill changes, expected-set protection and native recovery.
ADR-025 explains performer-attributed internally closed revenue and missing monetary facts.
ADR-026 explains original explicit objectives, pinned periods, exact targets and batched progress.
ADR-027 explains original effective-work interval declarations and remaining coverage limits.
PROJECT_STATUS.md records final verification counts and current checkpoint.
