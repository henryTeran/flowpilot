# ADR-023: Original declared employee certifications

Status: Accepted at controlled migration/API/component/Edge scope.

Certifications are separate signed, institute-owned facts. Each original records
employee, code, title, declared issuer and document reference, explicit issue date
or unknown date, aware validity start and explicit end or declared absence of an
end, reason, actor, original key and recording instant. These declarations do not
prove issuer authenticity, legal accreditation or permission to perform a service.
They never populate Employee.skills or EmployeeSkill implicitly.

The validity window is half-open. At the explicit reading instant a declaration
is upcoming, within its declared window or expired; a separate revocation takes
precedence. Nullable issue/end fields must be supplied explicitly. Unknown dates
remain unknown. UTC conversion rejects instants outside the supported calendar.
No rule relating issue date to validity is invented.

Only a signed institute manager can read or declare these sensitive facts.
Composite ownership constraints link the employee and revocation to their own
institute. The institute lock serializes key recovery, writes and bounded page
count/reading. A key retains its original actor and every normalized condition,
including dates at microsecond precision. A retry returns the original even after
its declared validity has passed or it has been revoked. Changed conditions or
actor are rejected. A correction creates a separate declaration; revocation is
a separate, single signed fact and never overwrites the original document.

The native manager workflow persists the exact pending request by institute and
actor before sending. After a lost response it reads the original key before any
new POST, validates scope, source, actor and terms, then requires a fresh bounded
page before clearing the request. Unknown or contradictory results retain the
request. Actor/token/disposal checks prevent a previous actor's late read from
posting or clearing another request. A definitive rejected POST may be corrected
explicitly. Institute civil time controls require explicit repeated-hour choices;
missing local times are rejected. The readonly employee profile displays the same
facts, with its own explicit read timestamp and no mutation controls.

The schema migration creates only the two new fact tables. Empty roundtrips are
supported; an online downgrade refuses any original or revocation history before
DDL. SQLite and PostgreSQL fixtures verify metadata parity and preserved facts.
No application database is migrated by these tests.

New configured certification requirements and expiry-aware assignment policy
would be separate explicitly configured scope, not an additional section 32 gate
(ADR-025). Native skill authoring/recovery is delivered in ADR-024.
Neither the SKILLS nor EMPLOYEE_360 gate is
closed by this unit. Workforce objectives, employee monetary/activity measures,
hours and commissions, plus physical-device and production acceptance, remain
explicitly open in WORKFORCE_GATE_AUDIT.md.
