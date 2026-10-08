# Smart Waitlist — Phase15

Authority: Master Plan section36. WAITLIST, WAITLIST_MATCHING and
AUTO_SLOT_DETECTION remain OPEN. Phase15A supplies a pure matching kernel;
15B adds retained authenticated demand declarations. Active waitlist lifecycle,
SQL capacity capture and native review remain unfinished.

## Contract and current implementation

`app/modules/waitlist/domain.py` accepts an explicit scoped customer/service
demand, captured duration, dated/evidenced customer availability, explicit employee
restriction and human constraints-review state. Unknown constraints refuse options;
a current duration differing from the declaration requires a fresh review.

Captured source facts expose current service skills/resource needs, bounded free
employee windows and resource reservations. Matching intersects customer and
employee windows at or after capture, delegates qualification to the existing
`has_required_skills` and complete resource allocation to `next_resource_window`.
Distinct resource units, half-open boundaries, unknown capacity and actual elapsed
duration retain the existing authority. All instants normalize to UTC, including
repeated civil hours. Each intersection yields its earliest complete option;
results sort by start then employee identity, not an invented business score.
Options are independent alternatives, not jointly reserved capacity.

Observed care history and dated service-follow-up email/SMS permission references
remain explicit context. Unknown history is not “never visited”; a refusal is not
a grant. Neither grants nor matches authorize sending. History/consent currently
do not rank or exclude candidates: final history-based rules and contact eligibility
must be specified from authoritative sources in the integration work below.

Source adapters must authenticate scope, registration, current lifecycle originals,
catalog activity, complete bookings/sessions/absences/resource occupancy and source
chronology. The pure input contract does not authenticate client-supplied facts.
There is no public endpoint accepting a caller's capacity snapshot. No opening
hours or physical attendance is inferred. A human “constraints confirmed” statement
is not machine verification of every real-world constraint.

## Remaining canonical work

| Section36 dimension | Current evidence | Required end-to-end work |
| --- | --- | --- |
| Service | Explicit demand/current service identity binding | Signed active-catalog and registration capture; retained demand authoring |
| Duration | Exact declared/current equality and full interval fit | Original duration source and correction/recovery UI |
| Customer availability | Ordered evidenced aware windows, exact intersection | Institute-calendar authoring, retained corrections/cancellation |
| Employee | Explicit allowed identities, known free windows | Owned current-source adapter, preferences and responsive review |
| Skills | Existing subset authority | Complete current requirement/qualification source capture |
| Resources | Existing distinct-unit allocator | Owned reservation inventory capture and revalidation before actual booking |
| Constraints | Unknown refuses; evidenced human review | Supported structured constraints, customer active-return conflicts and source uncertainty handling |
| History | Explicit observed/absent/unknown context with chronology | Sovereign care-history capture and explained declared policy, without inferred intent |
| Consents | Dated granted/refused/unknown service-follow-up context | Current retained lifecycle capture, explicit contact eligibility and refusal UX; no automatic dispatch |
| Auto slot detection | Pure earliest complete intersection | Signed bounded detection from complete current sources, invalidation/retry and audit evidence |
| Waitlist lifecycle |15B retained declarations, actor/key recovery, full-cohort verified audit, SQL migration and same-key concurrency | Revision/cancel transitions and active waitlist views; declarations alone are not active lifecycle |
| Product/release | No waitlist UI yet | Native manager desktop/tablet, authorization/tenant/replay/tamper tests; separate production/load/physical acceptance |

## Verification

Initial pure run:9 passed/1 failed; ordering assertion incorrectly compared the
entire retained source capture rather than the computed options. Source order is
preserved, while options must be deterministic; corrected assertion checks options
and outcome. A subsequent compatibility command used a nonexistent test filename
and collected nothing; it is not passing evidence.

Final focused run:11 passed0.98s, terminalexit0. Final combined kernel/existing
allocator regression:19 passed1.68s, terminalexit0, no failures/skips. Covers
joint intervals, touching/microsecond boundaries, two distinct resources, input
order, unknown/refused/granted context, foreign identities, duplicate sources,
unsafe copied models, expired windows and repeated Zurich civil hour. Existing
crypt deprecation only. No SQL fixture, migration, API or browser acceptance claimed.

## Phase15B — retained demand declarations

Manager-only `/api/v1/waitlist/institutes/{institute_id}` routes offer POST/GET
`/originals`, GET `/original-by-key` and GET `/originals/{original_id}`. Signed
actor and one capture clock are fixed by the server. Client-supplied actor, clock,
source or institute fields are forbidden. New writes verify owned registration,
registration chronology, active catalog duration and owned restricted employee
identities under the existing institute lock. Customer IDs are retained without a
live deletion foreign key; future matching must revalidate current registration.

Every declaration records its full normalized request, source registration/catalog
facts, actor, key and exact raw JSON/SHA256. Read verification binds SQL columns,
logical source/demand consistency, capture and explicit `declared_only` /
`no_booking_or_contact` claims. SHA detects alteration at this application boundary;
it does not authenticate an administrator who can rewrite all SQL facts.

Same-key recovery verifies the original before recapturing mutable customer/catalog
facts, then requires identical request and actor. A declaration remains recoverable
after its windows expire or the catalog changes. This does not make the old demand
currently eligible. Audits verify the whole retained cohort before returning a20-row
default page (maximum50). No update/delete route rewrites originals, and there is no
claim of database-enforced append-only storage.

Migration9f06c754aa3b follows8ef5b643992a. Empty online downgrade is supported;
offline downgrade or any retained history refuses removal. No persistent application
or production database was migrated. Deployment must apply the controlled migration.

First expanded run:20 passed23.75s with actual PostgreSQL enabled, terminalexit0.
Final strengthened six-module regression:37 passed60.29s, zero failures/skips,
terminalexit0 with SQLite and actual isolated PostgreSQL enabled. It includes the
existing allocator/scenario-original/closure-migration compatibility checks as well
as actual PostgreSQL same-key race, forced-flush rollback and
committed lost-acknowledgement recovery, signed SQLite HTTP routes, source changes,
25-row20/5 audit, off-page rehashed corruption and migration metadata/history guards.
Unsafe-copy tests intentionally produce Pydantic serializer warnings; existing crypt
deprecation remains. Frontend unchanged; no native waitlist or whole-project claim.

Next: explicit revision/cancellation lifecycle for retained demands, then capture
current sovereign SQL sources and expose authenticated matching review. Do not close
any Phase15 gate from declaration/pure-kernel evidence alone.
