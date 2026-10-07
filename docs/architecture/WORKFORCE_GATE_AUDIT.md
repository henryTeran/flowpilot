# Workforce gate audit — canonical section 32

Phase 11A implements the recorded Skill Matrix. It does not close Phase 11.
Inventory's physical and production gates remain open while this independent
authorized Workforce scope progresses.

| Requirement | Current authoritative evidence | Remaining work |
| --- | --- | --- |
| Skill Matrix | Workforce signed scoped endpoint, native Équipe matrix, bounded independent axes, explicit missing/unconfigured requirements; `test_workforce_matrix_11a.py`, `workforce.test.tsx`, `workforce.spec.ts` | Physical-device and production acceptance |
| Compétences | Existing `Employee.skills` / `EmployeeSkill` union and `ServiceRequirement`; protected audited resource configuration and the same predicate used by assignment and matrix | Native manager authoring/recovery and complete workforce integration |
| Disponibilité | Existing current-day planning availability read and native live board; skills alone never claim availability | A dedicated Employee 360 read/profile and scheduled absence integration |
| Planning | Existing institute-day planning, appointments, elapsed native timeline and selected-day agenda | Employee-specific calendar integrating recorded shifts and absences |
| Certifications | No certification/expiry authority has been delivered | Scoped explicit certification facts, validity and configured matching policy; never infer them from skill codes |
| Objectifs | No workforce objective authority has been delivered | Explicit manager-configured targets, periods/units and source-grounded progress |
| CA | Recorded performed employee attribution and internally closed invoice facts exist in Commerce; matrix does not calculate revenue | Employee-specific exact read preserving original invoice currency, corrections and unresolved external settlement |
| Occupation | Actual session and appointment execution facts exist; a planned schedule is not recorded attendance | Source-grounded employee intervals; a ratio needs a known hours denominator |
| Rebooking | Original execution/customer links and future appointment facts exist; no employee rebooking measure is delivered | Explicit definition and scoped recorded-event read; no inferred customer identity or predicted result |
| Commissions | No configured workforce commission ledger/rule authority is delivered | Explicit rates/basis/currency, original rule pinning, actual attributed source and protected correction/replay semantics |
| Absences | Current `absent` status exists; this is not a scheduled absence calendar | Signed scoped interval facts, conflict protection and integration with scheduling |
| Congés | No leave calendar is delivered | Explicit scheduled leave facts and lifecycle, using the same unavailability authority |
| Heures | Session duration exists; it does not establish an employee's shift or attendance | Recorded workforce hours and interval provenance; no inferred payroll or legal acceptance |

Gates remain:

- `EMPLOYEE_360`: OPEN — individual integrated profile and named measures pending.
- `SKILLS`: PARTIAL — recorded matrix and existing matching/configuration are
  verified; certification/native authoring and remaining acceptance are pending.
- `ABSENCES`: OPEN — scheduled facts and capacity integration pending.
- `COMMISSIONS`: OPEN — configured rules and source-linked calculations pending.

Next independent unit: signed original scheduled absence/leave facts with a
protected lifecycle, followed by integration into the existing capacity engine.
Do not create a second scheduler or derive a future absence from today's status.
Then finish the Employee 360 read/profile and explicit certification, objective,
hours and commission authorities. Existing payment settlement and physical
tablet/production blockers do not prevent these implementations.

ADR-020 explains bounded shared-source reads and their institute-lock tradeoff.
PROJECT_STATUS.md records final verification counts and current checkpoint.
