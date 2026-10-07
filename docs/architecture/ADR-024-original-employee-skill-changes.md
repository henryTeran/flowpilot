# ADR-024: Original signed employee skill configuration

Status: Accepted at controlled migration/API/component/Edge scope.

The manager's native skill editor uses the existing Employee.skills/EmployeeSkill
authority, shared skill predicate and protected resource configuration service.
It does not introduce a new qualification store or infer skills from declared
certifications. Codes remain explicit manager configuration, with existing
length, uniqueness and count bounds.

An original skill change records the employee, institute, exact expected skill
set, requested new set, signed actor, reason, original key and recording instant.
Inside the institute lock, original-key recovery precedes the current-state
comparison. A matching replay returns the original without applying its skill
set again. Changed actor or conditions are rejected. A new key requires the
current authoritative union to equal the explicitly reviewed expected set;
otherwise the manager must reread. Competing configurations cannot overwrite a
change made after their reading.

The existing service continues to reject skill removal required by assigned
ticket lines, active sessions or existing reservations. Its legacy/structured
synchronization and configuration event can now participate in the caller's
transaction. The original recovery fact and all skill changes commit together;
existing resource PATCH callers retain their previous commit behavior. No-op
reviews can retain an original fact without fabricating a changed configuration.

The native editor persists its actor/institute-scoped exact request before POST.
It recovers through original-key GET, verifies every original condition and
identity, then requires a fresh current skill read and operational refresh before
clearing. A later configuration is displayed as the current reading; recovery
never reapplies obsolete original conditions. Contradictory or unknown replies
retain the request. A failed fresh read can be retried while the request remains
frozen. Token, disposal and employee scope checks prevent stale reads from posting
or displaying a previous employee's skill set. Definitively rejected writes can
be explicitly corrected after rereading.

The new migration uses a composite employee/institute FK and scoped unique key.
Empty downgrade/upgrade roundtrips are supported. Offline downgrade is refused,
and any original history prevents removal before DDL. Owned SQLite/PostgreSQL
fixtures verify metadata parity and history preservation. Application databases
are not migrated by verification.

Physical-device and production acceptance remain open. Explicit certification
matching policy, objectives, employee revenue/occupancy/rebooking, hours and
commissions remain separate Workforce work; this unit does not close Phase 11.
