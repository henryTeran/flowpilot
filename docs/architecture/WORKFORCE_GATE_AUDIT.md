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
| Occupation | Manager day API and native selected-day profile retain actual source unions, declared denominator, exact covered/outside time, exclusions and floored recorded-time ratio; controlled API/component/Edge desktop/tablet verified | Physical/production acceptance; complete activity/attendance stays unknown |
| Rebooking | Signed original attribution/cancellation API, bounded declaration-day read and guarded profile retain source provenance and global counts; controlled signed workflows/Edge desktop/tablet verify readonly provenance, changed-target diagnostics and native original declaration/cancellation/lost-reply recovery | Physical/production acceptance; no inferred identity, absent-declaration failure or predicted return |
| Commissions | Internal owned closed-line capture and explicit gross-basis/rate/currency/scope/period/rounding contract with exact immutable per-line calculation; SQLite and actual PostgreSQL tests pass | Original configured rules, source-linked accrual/cancellation ledger, protected correction/replay, bounded native/profile integration and final acceptance |
| Absences | Signed manager-only original facts, capacity conflict protection, native authoring/recovery and employee calendar are verified on controlled API/component/Edge | Physical-device and production acceptance |
| Congés | Explicit `leave` intervals share the original authority, native cancellation/recovery and scoped employee/day calendar | Physical-device and production acceptance; no entitlement/payroll claim |
| Heures | Original signed completed effective-work intervals, separate cancellations, native manager lifecycle/lost-reply recovery, bounded history and selected-day employee read; exact union durations retain DST/microseconds and unknown attendance coverage | Physical/production acceptance; no inferred complete attendance, payroll or legal acceptance |

Gates remain:

- `EMPLOYEE_360`: OPEN — availability/skills/calendar profile foundations delivered;
  declared certifications, attributed gross revenue, original objectives/hours and recorded occupation and native recorded rebooking added; commissions and final acceptance pending.
- `SKILLS`: PARTIAL — recorded matrix and existing matching/configuration are
  verified with native original skill authoring/recovery; remaining workforce and physical/production acceptance is pending.
- `ABSENCES`: PARTIAL — scheduled original facts and capacity integration are
  implemented with native lifecycle/recovery and employee calendar; final acceptance remains pending.
- `COMMISSIONS`: OPEN — configured rules and source-linked calculations pending.

Section 32 requires certification facts and a Skill Matrix. A new credential
qualification policy is not an additional canonical gate. Existing explicit
skill requirements remain authoritative; new credential rules would require
explicit configuration and must not grant skills implicitly.
Bounded scoped actual-completion source and same-client target choice APIs now
support the native manager form; invalid/unknown/attributed choices stay explicit.
Protected original declaration/cancellation recovery is verified in controlled Edge.
ADR-030 now defines the verified commission source and exact arithmetic contract.
Next independent unit: original configured commission rules and source-linked accruals,
then protected native lifecycle and employee profile integration.
Do not create a second scheduler or derive a future absence from today's status.
Then finish the Employee 360 read/profile and commission authorities.
Existing payment settlement and physical
tablet/production blockers do not prevent these implementations.

ADR-020 explains bounded shared-source reads and their institute-lock tradeoff.
ADR-021 explains original interval/cancellation facts and capacity arbitration.
ADR-022 explains scoped employee calendar sources, actual/planned distinction and snapshot paging.
ADR-023 explains original declared certifications, separate revocations and recovery.
ADR-024 explains original skill changes, expected-set protection and native recovery.
ADR-025 explains performer-attributed internally closed revenue and missing monetary facts.
ADR-026 explains original explicit objectives, pinned periods, exact targets and batched progress.
ADR-027 explains original effective-work interval declarations and remaining coverage limits.
ADR-028 explains recorded occupation, exact source intersections and incomplete coverage.
ADR-029 defines explicit recorded rebooking and the required original source/booking capture.
ADR-030 defines explicit recorded gross-line commission terms and exact captured calculation.
PROJECT_STATUS.md records final verification counts and current checkpoint.
