# Smart Waitlist — Phase15

Authority: Master Plan section36. WAITLIST, WAITLIST_MATCHING and
AUTO_SLOT_DETECTION remain OPEN. Phase15A supplies a pure matching kernel;
15B adds retained authenticated demand declarations;15C adds explicit activation,
revision and cancellation. SQL capacity capture and native review remain unfinished.

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
| Waitlist lifecycle |15B declarations;15C explicit activation/revision/cancellation, original/key recovery, verified chains, active/cancelled counts and paging | Native authoring/recovery and matching integration; declarations alone are not active lifecycle |
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

## Phase15C — explicit active lifecycle

A declaration stays `declared_only` until an explicit activation event. POST
`/lifecycle/originals` takes the root original ID/fingerprint, exact previous event
ID/fingerprint (null for initial activation), action and selected target original
ID/fingerprint, reason and replay key. Every event fixes signed actor/server capture
and records `waitlist_state_only_no_booking_or_contact`. Target declarations keep
the same registered customer; a revision can explicitly select a different service
or availability declaration. Cancellation preserves the currently selected target.
Cancelled roots cannot be reopened; a genuinely new request needs a new root.

Activation/revision revalidate current registration, active catalog duration, owned
employee restrictions and remaining future availability, retaining the registration/
catalog/restriction source used for that transition. This is not a slot capacity or
consent check. Unknown constraints may be recorded in an active request but cannot
yield eligible options under the matching kernel. Cancellation does not recapture
current eligibility, so expired windows/inactive services do not prevent cancellation.
An expired request can remain administratively active until cancelled; matching must
still clip/refuse expired availability. No automatic expiry or hidden reservation.

Each event is retained with raw JSON/SHA and bound SQL columns. Complete chains
verify references to the independent demand originals, predecessor hash and capture,
one first activation, unique successors, no orphans/cycles/branches, same customer,
current target and terminal cancellation. Equal capture times follow causal links,
not ID sorting. SQL unique `(institute, root, previous)` uses an empty sentinel for
the first event, so initial activation is protected as well as later successors.
The existing institute lock serializes writes; stale predecessors are rejected.

Key replay verifies the retained chain/request/actor before recapturing current
eligibility. GET `/lifecycle/original-by-key`, `/lifecycle/originals/{event_id}` and
`/lifecycle/states/{root_id}` provide independent event/state reads. GET `/lifecycle`
verifies the entire activated-root cohort before returning20/default50/max states,
with active/cancelled totals separate from pages. Unactivated declarations remain
in their independent audit, not this active lifecycle. Complete raw histories are
returned for each selected root; large-history memory/load behavior is unverified.

Migrationa017d865bb4c follows9f06c754aa3b. Empty online down/up is supported;
offline or populated-history downgrade refuses removal. No persistent application
or production database migrated. No SQL administrator authenticity or append-only
trigger guarantee; application routes do not rewrite/delete retained originals.

Final seven-module regression:41 passed130.35s, zero failures/skips, terminalexit0
with SQLite and actual isolated PostgreSQL enabled. Includes demand/kernel/allocator
and earlier closure-migration compatibility. Proves explicit lifecycle, signed
HTTP writes/reads/denials, independent by-ID/key/state reads, stale-version rejection,
25-root20/5 full-cohort paging and off-page rehashed source refusal. Actual PostgreSQL
same-key and conflicting-successor races, forced rollback, committed lost-ack recovery,
chain/source/clock/claim tamper, plus SQLite/PostgreSQL metadata and guarded down/up
are covered. Two intentional unsafe-copy serializer warnings plus crypt deprecation.
Frontend unchanged; no native waitlist, full-project or production acceptance claim.

The initial runs (13 passed/2 failed and28 passed/2 failed) found two older15B
migration assertions pinned to the previous head;
the schema/data/history guard remained intact. Those assertions now compare the
actual canonical Alembic head rather than a historical checkpoint's revision.

Next: capture current sovereign SQL capacity/history/consent/customer-booking facts,
apply explained constraints and expose authenticated matching, then native waitlist
authoring/recovery/review. All three Phase15 gates remain OPEN.
