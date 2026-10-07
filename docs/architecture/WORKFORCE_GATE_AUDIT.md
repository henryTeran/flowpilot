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
| Compétences | Existing `Employee.skills` / `EmployeeSkill` union and `ServiceRequirement`; protected audited resource configuration and shared assignment/matrix predicate; native original-key manager changes compare the reviewed expected set and recover without overwriting later configuration | Final regression and physical/production acceptance |
| Disponibilité | Existing availability engine and live board consume recorded absences; native employee profile exposes the same current reading at an explicit timestamp independent of selected calendar day | Final regression and physical/production acceptance |
| Planning | Institute-day planning plus native employee/day calendar integrates booked appointments, execution facts and original/cancelled absences; original completed-hours journal is integrated separately without inventing a planned roster; overnight, DST and skipped days retain explicit UTC boundaries | Final regression and physical/production acceptance |
| Certifications | Original signed institute/employee declarations, explicit issue/end unknowns, half-open validity and immutable separate revocations; native manager lifecycle/recovery and readonly profile | Final acceptance; never infer credentials from skill codes or automatically grant a skill. New credential matching rules require explicit configuration and are optional future scope |
| Objectifs | Original signed manager targets, pinned civil/UTC periods, explicit gross-currency or actual-completed-session measure, exact targets, separate cancellations, bounded batched progress API, native manager lifecycle/lost-reply recovery and readonly employee profile | Physical/production acceptance |
| CA | Bounded manager employee/day API and native profile read performer-attributed retained internally closed lines, separate exact currencies and missing data; SQLite/PostgreSQL/component/Edge checks pass | Physical/production acceptance; no external settlement or allocated refund/net-revenue claim |
| Occupation | Manager day API and native selected-day profile retain actual source unions, declared denominator, exact covered/outside time, exclusions and floored recorded-time ratio; controlled API/component/Edge desktop/tablet verified | Physical/production acceptance; complete activity/attendance stays unknown |
| Rebooking | Signed original attribution/cancellation API, bounded declaration-day read and guarded profile retain source provenance and global counts; controlled signed workflows/Edge desktop/tablet verify readonly provenance, changed-target diagnostics and native original declaration/cancellation/lost-reply recovery | Physical/production acceptance; no inferred identity, absent-declaration failure or predicted return |
| Commissions | Owned closed-line capture/exact calculation plus signed original configured rules, pinned civil/UTC periods, separate rule cancellations, source-linked accrual/cancellation originals with pinned exact calculation, cross-rule active source protection, original recovery, bounded employee journals and exact recorded-day amounts/counts per currency and bounded rule-specific source previews; original/day/choice frontend guards recompute exact arithmetic, counters and raw previews; native explicit rule and source-linked accrual/cancellation/lost-reply recovery plus exact recorded-day employee profile pass controlled checks | Final requirement/regression and physical/production acceptance |
| Absences | Signed manager-only original facts, capacity conflict protection, native authoring/recovery and employee calendar are verified on controlled API/component/Edge | Physical-device and production acceptance |
| Congés | Explicit `leave` intervals share the original authority, native cancellation/recovery and scoped employee/day calendar | Physical-device and production acceptance; no entitlement/payroll claim |
| Heures | Original signed completed effective-work intervals, separate cancellations, native manager lifecycle/lost-reply recovery, bounded history and selected-day employee read; exact union durations retain DST/microseconds and unknown attendance coverage | Physical/production acceptance; no inferred complete attendance, payroll or legal acceptance |

The controlled gate audit is distinct from physical-device/production acceptance.
At commit `85800ec`, all 28 Phase 11 backend test files pass on the owned SQLite/
actual PostgreSQL validation fixtures: 83 tests, zero failures/skips (517.40s).
All 16 signed native Workforce browser spec files pass on Edge desktop and touch
tablet emulation: 44 scenarios, zero failures/skips (5.6m). The launcher rebuilds
the current frontend and removes only its owned temporary database directory.
The preceding canonical frontend run contains 227 passing tests; no source change
is introduced by this documentation audit. All mapped source/test paths exist.

- `EMPLOYEE_360 = PASS` (controlled functional evidence) — all twelve canonical
  subjects have verified shared-source/native bindings, including commissions.
- `SKILLS = PASS` (controlled functional evidence) — recorded matrix, shared
  matching and native original expected-set authoring/recovery are verified.
- `ABSENCES = PASS` (controlled functional evidence) — original absence/leave
  facts, capacity integration, native recovery and employee calendar are verified.
- `COMMISSIONS = PASS` (controlled functional evidence) — explicit original rules,
  exact source-linked accrual/cancellation, bounded choices and native/profile
  workflows are verified.

These four results permit the next canonical functional implementation phase.
Physical-device, production migration/operations and complete-project acceptance
remain OPEN in their existing gates. Neither the full backend test suite nor
unrelated browser specs are claimed by this scoped regression.

## Executable requirement map

All paths below are relative to the repository's backend/frontend test or source
directories. Each row identifies an actual implementation and executable test
family; its current run result is recorded in `PROJECT_STATUS.md`.

| Canonical subject | Shared authority and native binding | Executable coverage |
| --- | --- | --- |
| Disponibilité | `workforce/calendar.py` calls the existing `scheduling/service.py` availability engine at the header's current reading instant; `EmployeeCalendarPanel.tsx` separates this from the selected day | `test_employee_calendar_11d.py`; `employee-calendar.spec.ts` |
| Planning | `calendar.py` unions retained appointments, sessions and original/cancelled absences; `EmployeeCalendarPanel.tsx` preserves planned versus actual clocks and bounded pages | `test_employee_calendar_11d.py`; `employee-calendar.spec.ts` |
| Compétences / Skill Matrix | `workforce/service.py`, shared scheduling matching, `skill_changes.py`; `SkillMatrixPanel.tsx` and `SkillEditorPanel.tsx` | `test_workforce_matrix_11a.py`, `test_skill_changes_11f.py`, `test_skill_change_migration_11f.py`; `workforce.spec.ts`, `skill-editor.spec.ts` |
| Certifications | `certifications.py` and original separate revocations; `CertificationPanel.tsx` plus its calendar readonly binding | `test_workforce_certifications_11e.py`, `test_certification_migration_11e.py`; `certifications.spec.ts` |
| Objectifs | `objectives.py`, explicit pinned targets and batched progress; `ObjectivePanel.tsx`, `EmployeeObjectivesPanel.tsx` | `test_workforce_objectives_11i.py`, `test_objective_migration_11i.py`; `objective-lifecycle.spec.ts`, `employee-objectives.spec.ts` |
| CA | `revenue.py` retains performer-attributed internally closed lines, missing amounts and separate currencies; `EmployeeRevenuePanel.tsx` | `test_employee_revenue_11g.py`; `employee-revenue.spec.ts` |
| Occupation | `occupation.py` intersects retained actual source unions with the declared-hours denominator, preserving unknown complete activity/attendance; `EmployeeOccupationPanel.tsx` | `test_occupation_11q.py`, `test_workforce_interval_math_11p.py`; `employee-occupation.spec.ts` |
| Rebooking | `rebooking_sources.py`, `rebooking.py`, `rebooking_day.py`, `rebooking_options.py`; `RebookingPanel.tsx`, `RebookingChoices.tsx`, `EmployeeRebookingPanel.tsx` | `test_rebooking_sources_11t.py`, `test_rebooking_11u.py`, `test_rebooking_migration_11u.py`, `test_rebooking_day_11v.py`, `test_rebooking_options_11y.py`; `rebooking-write.spec.ts`, `employee-rebooking.spec.ts` |
| Commissions | `commission_sources.py`, `commission_rules.py`, `commissions.py`, `commission_day.py`, `commission_options.py`; `CommissionRulePanel.tsx`, `CommissionPanel.tsx`, `CommissionChoices.tsx`, `EmployeeCommissionPanel.tsx` | `test_commission_sources_11ac.py`, `test_commission_rules_11ad.py`, `test_commission_rule_migration_11ad.py`, `test_commissions_11ae.py`, `test_commission_migration_11ae.py`, `test_commission_day_11af.py`, `test_commission_options_11ag.py`; `commission-rule-write.spec.ts`, `commission-write.spec.ts`, `employee-commissions.spec.ts` |
| Absences | `absences.py`, shared scheduling/capacity guards; `AbsencePanel.tsx`, `EmployeeCalendarPanel.tsx` | `test_workforce_absences_11b.py`, `test_absence_migration_11b.py`; `absences.spec.ts`, `employee-calendar.spec.ts` |
| Congés | Explicit `leave` kind in the same original absence authority and separate cancellation; native absence/calendar binding | Same absence/leave suites above; no inferred allowance/payroll |
| Heures | `work_intervals.py`, `work_hours.py`, `interval_math.py`; `WorkIntervalPanel.tsx`, `EmployeeWorkHoursPanel.tsx` | `test_work_intervals_11l.py`, `test_work_interval_migration_11l.py`, `test_work_hours_11m.py`, `test_workforce_interval_math_11p.py`; `work-interval-lifecycle.spec.ts`, `work-hours.spec.ts` |

The matrix remains available to signed reception within its institute; sensitive
employee profiles and original lifecycle routes require the signed manager.
The shared institute lock protects scoped snapshot reads/writes. Test fixtures
use isolated owned databases/schemas; passing migration tests do not mean a real
application database was migrated. Unknown rights, attendance/activity coverage,
payment settlement and optional credential matching remain explicitly unknown.

Section 32 requires certification facts and a Skill Matrix. A new credential
qualification policy is not an additional canonical gate. Existing explicit
skill requirements remain authoritative; new credential rules would require
explicit configuration and must not grant skills implicitly.
Bounded scoped actual-completion source and same-client target choice APIs now
support the native manager form; invalid/unknown/attributed choices stay explicit.
Protected original declaration/cancellation recovery is verified in controlled Edge.
ADR-030 now defines the verified commission source and exact arithmetic contract.
Original signed rule creation/cancellation/recovery now has controlled API/migration evidence.
Source-linked accrual/cancellation and PostgreSQL active-source/replay arbitration now pass controlled checks.
Exact employee recorded-day read now passes controlled SQLite/PostgreSQL scope, chronology and snapshot tests.
Bounded rule-specific source choices and exact eligible previews now pass controlled SQLite/PostgreSQL checks.
Frontend original/rule/calculation/day guards now pass controlled compatibility/build checks.
Exact choice guards now independently verify raw source/preview bindings and exclusion priority.
Native configured-rule lifecycle now has controlled component and signed Edge creation/cancellation recovery evidence.
Readonly recorded-day employee commission profile now has controlled exact-currency/cancellation/isolation evidence.
Native source-linked accrual/cancellation and committed-lost-reply recovery now have
controlled signed desktop/tablet acceptance. Ticket-number display keeps source selection identifiable.
The requirement map and current scoped regression now verify the controlled
Phase 11 functional gates. Next canonical unit: Phase 12 CRM scope/source audit.
Do not create a second scheduler or derive a future absence from today's status.
No additional independent scheduler, inferred roster, entitlement or credential
qualification rule is introduced to manufacture a gate result.
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
