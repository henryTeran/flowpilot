# Smart Waitlist — Phase15

Authority: Master Plan section36. WAITLIST, WAITLIST_MATCHING and
AUTO_SLOT_DETECTION remain OPEN. Phase15A supplies a pure matching kernel;
15B adds retained authenticated demand declarations;15C adds explicit activation,
revision and cancellation;15D adds authenticated selected-version SQL matching.
15E adds whole-active-waitlist conditional detection;15F integrates core queue
allocations as virtual constraints;15G adds native retained-declaration history;
15H adds protected demand-intent transport;15I adds native declaration authoring
and recovery;15J adds native retained lifecycle history;15K adds protected native
activation/revision/cancellation and same-key recovery;15L adds current matching
and detection browser contracts;15M adds native selected-version matching and
whole-active detection review. Canonical Phase15 acceptance audit remains open.

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
a grant. Neither grants nor matches authorize sending.15D applies explicit
review/observed-care/no-recorded-care and review/recorded-grant policies;15L checks
those refusal/source relationships in browser contracts. 15M adds native explained policy
selection and source review; actual contact authority stays separate.

Source adapters must authenticate scope, registration, current lifecycle originals,
catalog activity, complete bookings/sessions/absences/resource occupancy and source
chronology. The pure input contract does not authenticate client-supplied facts.
There is no public endpoint accepting a caller's capacity snapshot. No opening
hours or physical attendance is inferred. A human “constraints confirmed” statement
is not machine verification of every real-world constraint.

## Remaining canonical work

| Section36 dimension | Current evidence | Required end-to-end work |
| --- | --- | --- |
| Service |15B retained owned registration/catalog proof;15D signed current active-catalog capture;15I native explicit catalog selection | Current matching review |
| Duration |15D current/declared equality and full interval fit;15I catalog-derived declaration and correction/recovery UI | Current matching review |
| Customer availability | Ordered evidenced windows,15D intersection and recorded customer booking/session blockers;15I explicit institute-calendar windows | Current matching review |
| Employee | Explicit restrictions;15D owned current core free-window capture | Responsive review, additional supported preferences |
| Skills |15D current existing requirement/qualification authority | Native proof review |
| Resources |15D owned reservation inventory/allocator;15F core projected queue resource occupations | Native evidence; revalidation before any actual booking |
| Constraints | Unknown human review refuses;15D customer conflicts, overdue capacity/source refusal | Additional supported structured constraints, current queue implications and native review |
| History |15D sovereign care capture, latest observed episode/diagnostics and explicit review/observed/no-recorded requirement | Native explained policy; no inferred intent or complete real-history claim |
| Consents |15D current retained lifecycle source, channel-specific service-follow-up grant/refusal/unknown; future declaration stays unknown | Native refusal/source UX; actual contact authorization/delivery stays separate |
| Auto slot detection |15D selected-version intersections;15E whole-cohort capture/paging;15F queue allocations | Native source invalidation/evidence and release/load verification |
| Waitlist lifecycle |15B declarations;15C explicit activation/revision/cancellation, original/key recovery, verified chains, active/cancelled counts and paging;15I native declaration authoring/recovery;15J native causal history;15K native transitions/recovery | Current matching integration; declarations alone are not active lifecycle |
| Product/release |15G?15K native manager history, declaration and lifecycle authoring/recovery; signed desktop/tablet tests | Native current matching/detection and separate production/load/physical acceptance |

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

## Phase15D — authenticated current-source matching

GET `/lifecycle/states/{root_id}/matching` requires the expected current lifecycle
event ID/full fingerprint, explicit aware ISO horizon, email/SMS channel and explicit
history/permission review policy. Manager/exact-institute scope remains required.
Stale version refuses; cancelled roots produce an explicit unavailable result.
There is no endpoint accepting a caller's capacity/history/consent snapshot.

One institute-locked server clock pins current registration, active service/duration,
existing qualification facts, core employee availability, absences and resource
inventory/reservations. Active booking/session ownership and positive intervals,
typed skill/resource configuration, reservation ownership and observed absence/
cancellation clocks are validated before core readers can omit malformed sources.
An active booking in progress beyond its recorded end gives unknown employee
capacity; an overdue current customer booking/session gives unknown customer capacity.
Unreleased expired resource occupancy stays unknown under the existing authority.

Customer booking/session intervals are subtracted using the existing free-window
kernel without rewriting the retained availability declaration. Employee/source
windows are clipped to the explicit horizon, then the matching kernel intersects
them with customer availability and solves complete distinct resource units. Current
duration changes require a fresh declaration; machine service without configured
resource needs refuses. Returned options are independently feasible conditional
alternatives, not jointly reserved or exhaustive possible start times.

The sovereign CRM actual-care capture observes ticket-linked care since current
registration up to capture. Diagnostics make recency/history unknown rather than
using a surviving subset. Clean zero episodes means no care recorded in that scope,
never “never visited”. Explicit policy may require observed care or no recorded care;
unknown refuses either requirement. Current channel-specific service-follow-up
permissions come from retained lifecycle declarations independently of birthday
calendar presence. Future declarations remain unknown. Requiring a recorded grant
refuses unknown/refused states, but even a grant is not contact authorization or
proof of a usable contact coordinate. Review-only policy invents no eligibility rule.

Evidence exposes care/source diagnostics, current permission original/reason,
employee availability reasons, customer conflict source IDs and waiting-ticket
count. Opening hours, physical attendance, complete real care/obligation history,
contact authority and reservation remain unproven. This read uses the existing
booking availability authority, not the wait-time projection of unreserved waiting
tickets. Waiting/assigned queue implications must be reviewed and integrated in
remaining detection work; no claim that a queue was displaced or fully accommodated.
Captured results are current snapshots that require revalidation before an action.

Initial16 passed19.32s. Final seven-module regression66 passed65.28s, no failures/
skips, terminalexit0 with SQLite and actual isolated PostgreSQL. Covers signed API
scope, ISO/epoch refusal, pin/stale/cancel guards, current source changes, independent
permission calendar absence/future grants/refusals, observed/invalid care, customer
booking/session conflicts, absence/resource reservation fit, overdue uncertainty,
missing machine configuration and unchanged original/reservation counts. Includes
existing lifecycle/demand/allocator/availability compatibility. Two intentional
unsafe-copy serializer warnings from15B tests plus existing crypt deprecation.
No schema changes (head a017d865bb4c), persistent database migration, frontend/native
waitlist, full-project regression or production acceptance claimed.

## Phase15E — whole-active-waitlist detection

Manager/exact-institute GET `/detection` requires explicit aware ISO horizon,
channel and history/permission policy, with20/default50/max output pages. A single
server clock and institute lock pins every current lifecycle/source review. The
private capture argument of the source adapter is available only to trusted internal
aggregate code; HTTP accepts no observation clock or source snapshot.

Every activated root's complete retained chain is verified. Cancelled roots are
counted separately; every active root's current matching sources are evaluated
before paging. Totals count roots with/without options, with exact reason counts,
not distinct customers, jointly feasible appointments or distinct physical slots.
Multiple requests can independently propose the same capacity. No allocation,
booking, contact, monetary total or inferred priority follows from these counts.
Unactivated declarations stay outside detection and in their own retained audit.

Output paging does not bound the verification cohort. Off-page corruption refuses
the read rather than silently accepting a clean displayed subset. Internal reads
revalidate their selected lifecycle event at the shared capture; mismatched clocks
or state refuse. Full source review is recomputed per active root, so query count,
whole-cohort history/resource memory and production load remain unverified. This
is output-bounded conditional detection, not a bounded-work or performance claim.

Fresh three-module regression:20 passed79.31s, no failures/skips, terminalexit0
with SQLite and actual isolated PostgreSQL enabled; existing crypt deprecation only.
Tests create26
activated roots, cancel one, verify25 active reviews20/5 and a single clock without
per-row recapture, exercise full-cohort grant-required refusal, off-page rehashed
corruption, signed tenant/role checks and unchanged resource reservations on SQLite
and actual isolated PostgreSQL. Existing selected-source and pure-kernel regression
are included. No new schema, frontend, native waitlist or production gate claim.

## Phase15F — projected queue constraints

An optional private observer in the existing pure queue engine exposes each selected
employee/interval/resource match to the trusted source adapter. The original engine
still owns FIFO/assignment precedence, skills, whole quantities and joint resources;
no optimizer is copied and existing public waiting-projection DTOs stay unchanged.
The observer performs no allocation write. Source capture validates queued arrival,
owned assignment, line service/positive duration/quantity and complete projection
cohort. Missing machine configuration contributes unknown queue capacity.

Selected projected intervals are subtracted from employee windows and added to
resource timelines as virtual occupations. A linked queued customer also receives
the projected customer interval blocker. Persisted reservations remain intact;
virtual occupations never release or create a reservation. The same joint kernel
then finds conditional waitlist options using these augmented sources. Any queued
ticket that cannot be projected makes queue capacity unknown and refuses options,
rather than treating the omitted work as free capacity. This is a conservative
review rule, not proof of physical queue execution or a dispatch/assignment policy.

Evidence returns projected ticket/employee/interval/resource identities and the
unprojectable count alongside existing waiting count and source diagnostics. All
options remain independent alternatives; batch requests do not reserve jointly.
Core queue projection is a conditional current snapshot; opening hours, physical
attendance and exact future arrivals still require review and action revalidation.

Initial compatibility34 passed82.07s and expanded seven-module queue/source/detection/
kernel/waiting/resource/revenue-slot regression40 passed135.02s, terminalexit0,
no failures/skips with actual PostgreSQL enabled. A final strengthened queue/source/
detection run follows a partition guard: tickets lacking machine configuration
are counted as unknown, excluded from known queue allocations, and never counted
twice. Final strengthened three-module regression11 passed113.35s, no failures/skips,
terminalexit0 with SQLite and actual isolated PostgreSQL; crypt deprecation only.
New SQLite/PostgreSQL cases verify shared-room
occupation by another employee, projected occupation of the selected employee,
whole quantity doubling, unknown qualification and restoration after cancellation,
with unchanged physical reservations. No schema/frontend/persistent DB changes.

## Phase15G — native retained declaration history

Pilotage exposes an explicit manager-only20-row original-history reader. It makes
no mount request and distinguishes retained declarations from currently active
requests, capacity or permission. Institution-zone dates, declared windows/duration,
constraints known/unknown, captured actor/reason and folded original/source proof
are visible. Original JSON and long proofs wrap; controls reuse44px/full-width styles.
Reads mask old evidence while pending and clear it on error. Request sequence,
unmount, actor token/role and institute/timezone remount guards reject stale replies.

Browser validation checks exact DTO keys, full Python-compatible raw JSON SHA256,
scope, source/demand equality, registration/capture microsecond chronology, positive
ordered non-overlapping windows, unique employee restrictions, explicit constraints,
strict no-action/declaration state, safe counts and exact page cardinality/order.
Old expired availability stays valid as historical declaration, never current
eligibility. Whole-cohort verification remains the server's authority, not a browser
claim that off-page JSON was returned or authenticated against a SQL administrator.

Pure backend DTO generator creates the checked-in Unicode/multiline vector without
SQL/application I/O. Initial TypeScript build exposed callback narrowing of an unknown
array; fixed by binding the validated array. Initial component run3pass/1fail asserted
the retry before asynchronous SHA completion; it now waits for read completion.
Final focused4 passed3.25s and complete frontend406 passed78.60s, no failures/skips,
terminalexit0. Final TypeScript/Vite production build passed172 modules.

Native actual signed backend Edge desktop/touch landscape tablet:2 passed1.7m,
terminalexit0 and owned temporary database removed. API-created customer/declarations
produce25 then50 originals, real20/5 and20/20/10 paging; this is not native authoring.
Native checks prove no mount read, folded fingerprint/unknown constraints, invalid
reply hiding/retry,44px controls, width>=600/no document overflow and zero activated
lifecycle roots after history reads. Both final original-card captures inspected:
institute dates and wrapped proof are readable. No backend/schema change (head
a017d865bb4c), persistent migration, whole-project/physical/production acceptance.

Next: protected native demand authoring and original/key recovery, followed by
explicit lifecycle transitions and matching/detection policy/evidence review. All
three Phase15 gates remain OPEN; full26-phase goal stays active.

## Phase15H — protected demand-intent transport

`frontend/src/waitlist-intent.ts` freezes the explicit request in actor/institute
scoped storage before any request. Every attempt first reads the original by key;
only literal null permits POST. Reload/lost acknowledgement reuses frozen terms,
even if the draft changes. Full raw SHA, exact source/actor/request binding and
independent key and ID reads must agree before cleanup. Equivalent timezone offsets
compare as exact microsecond instants; expired frozen windows remain recoverable,
while the backend still checks new declarations against its current clock.

Unreadable storage or persistence failure blocks writes. Same-storage concurrent
instances share a flight guard. Session invalidation stops late requests/cleanup.
Only definitive POST400/404/422 rejection offers correction, and a fresh null-key
read is required before releasing frozen terms. Recovery/confirmation read errors,
unknown acknowledgements, divergent receipts or changed storage preserve the intent.
Correction recovers an intervening retained original instead of discarding it.

This is a dependency-injected transport contract: it has no native form, role UI,
customer/catalog/calendar picker, lifecycle action, booking or contact. Existing
backend authorization and source validation remain authoritative. Storage coordination
does not claim cross-tab serialization; server idempotency remains necessary.
Native15G evidence is unchanged, not new native authoring evidence. Backend/schema
and persistent databases are unchanged. Next: explicit institute-calendar demand
form using this transport, recovery UX, then lifecycle and matching/detection review.

Eleven protocol tests cover persistence-before-I/O, lost acknowledgement/reload/no
second POST, valid-but-wrong receipts, independent receipt changes, definitive
rejection/correction, read errors, intervening retained receipt, invalid/quota storage,
undefined recovery, changed intent, concurrent instances and session changes at each
network boundary. Focused protocol plus original contracts:13 passed1.42s. Complete
frontend:417 passed94.23s, no failures/skips, terminalexit0. TypeScript/Vite production
build passed172 modules, terminalexit0. All three Phase15 gates remain OPEN.

## Phase15I — native declaration authoring and recovery

Manager-only Pilotage writer uses the existing customer picker (including explicit
native registration), loaded active catalog duration and owned employee choices.
Customer, service, restrictions, constraints and civil dates/times start empty;
unknown constraints is an explicit choice, not a silent default. One to64 windows
must be ordered, positive, non-overlapping and retain a future end at declaration. Availability,
reason and confirmed-constraint evidence require explicit text. No duration, customer
identity, employee capacity, permission or booking is invented.

The existing institute calendar resolves civil date/time without the browser's local
zone. Missing/invalid institution timezone blocks new declarations. Skipped hours
refuse; repeated hours require an explicit occurrence. Changing civil input resets
that occurrence. Frozen original terms remain recoverable even after expiry or a
timezone/catalog change; fresh source validation remains the backend's authority.

15H transport freezes before I/O, recovers key-first and independently rereads
key/ID/full-SHA/actor/request before showing success. Lost acknowledgement locks
draft fields and exposes the immutable request and same-key retry across reload.
Only definitive POST rejection enables a fresh key check before correction; any
intervening retained original is recovered. Invalid saved intent blocks new writes.
Scope/timezone/token remounts and current actor/role/unmount guards suppress stale
network continuation and receipt publication. Customer-picker callbacks are scoped.

Verified success clears intent, exposes institution-zone windows, known/unknown
constraints, actor/capture and folded original/source/full fingerprint. History is
invalidated after confirmed authoring and remains an explicit read; a new declaration
resets all draft choices. No activation, booking, assignment, reservation, contact,
opening-hours verification or current source eligibility follows from conservation.

Initial focused19 passed5.95s; complete frontend423 passed98.56s. Successful explicit
repeated-hour instant and prior-history invalidation coverage were strengthened;
final writer7 passed4.84s and complete frontend424 passed95.86s, no failures/skips,
terminalexit0. Initial production TypeScript/Vite build passed175 modules; final
native harness rebuilds production sources. Two initial native timeouts arose from
exact label lookup for catalog select; two subsequent failures after committed POST
arose from filled-textarea label lookup. Role-based test locators fixed these;
next native2 passed40.9s. Visual QA found the inherited customer search target
below44px; scoped input/select minimum and assertions for all visible form controls
now enforce44px. This CSS-only correction follows the424-test logic baseline.

Final rebuilt actual signed backend Edge desktop/touch landscape tablet:2 passed
43.8s, no failures/skips, terminalexit0; owned temporary database removed. Native
customer registration and two-window authoring verify catalog duration, institute
calendar-to-UTC normalization, saved terms before POST, committed lost acknowledgement,
field lock, reload recovery with one POST and three independent reads, full raw SHA
and source, explicit history reread, no automatic activation and empty new-draft
reset. All six final form/frozen/receipt captures inspected individually: readable
dates, wrapped original/source proof, region width>=600,44px controls and no overflow.
DST/correction/invalid storage/late authority cases are DOM/protocol coverage, not
native visual evidence. Backend/schema unchanged (heada017d865bb4c); no persistent
migration, physical device/provider/load/production acceptance. All three Phase15
gates remain OPEN; next native explicit lifecycle transitions and version/key recovery,
then current matching/detection policy and source review. Full26-phase goal stays active.

## Phase15J — native retained lifecycle history

Manager-only Pilotage reader explicitly fetches20-row lifecycle pages, with no mount
I/O. Total/active/cancelled counts describe retained request roots, not distinct
customers or feasible appointments. Current selected declaration, institution-zone
availability, duration and confirmed/unknown constraints are visible. Administrative
active state is not eligibility. Cancelled chains remain terminal and readable.
Folded proof shows causal actions, captured actor/reason/clock, original ID/key/full
SHA, selected declaration reference and retained activation/revision registration,
catalog duration and restrictions. Cancellation explicitly has no new eligibility
capture. Raw event/root/current originals remain inspectable and wrap.

Browser validates exact request/event/state/audit contracts, complete raw SHA,
safe count partitions and exact20-row cardinality/root order, unique action IDs and
keys across returned roots, one customer across root/current/source, predecessor
ID/full fingerprint, nondecreasing microsecond clocks, initial activation, changed
revision target, preserved cancellation target and terminal state. Equal clocks
follow causal links, never event-ID sorting. Returned root/current declarations
bind known target fingerprints, captured source fields and historical future-window
conditions. Intermediate replacement originals omitted from the state response
remain opaque references: server15C verifies their source/chronology and all off-page
chains before paging. This is consistency evidence, not SQL-admin authenticity,
current calendar/capacity, contact permission or inferred automatic action.

Pending/error masks prior evidence; retry and request/unmount/role/token/institute/
timezone guards suppress stale reads. Pure backend typed DTO generator creates the
Unicode/multiline/equal-clock vector without SQL or application startup. Four pure
and two component tests cover rehashed source/target/causal contradictions, raw
tamper, duplicate keys, terminal/order/predecessor violations, partitions, page and
capture bounds, corruption mask/retry and late scope/timezone/role replies. Focused
lifecycle plus prior writer13 passed8.14s; full frontend430 passed95.48s, no failures/
skips, terminalexit0. TypeScript/Vite production build passed177 modules, terminalexit0.

Final rebuilt actual signed backend Edge desktop/touch landscape tablet2 passed
2.0m (19.5s/13.6s), no failures/skips, terminalexit0; owned tempDB removed. API fixtures
create25 then50 activated roots, one revised/cancelled chain per profile and additional
unactivated declarations; these API transitions are not native transition authoring.
Native reads prove20/5 and20/20/10 paging with unique roots,24/48 active and1/2 cancelled,
causal three-action/current-replacement proof, unknown constraints, full original/source
fingerprints, corrupt terminal-state mask/retry,44px controls, region width>=600/no
overflow and unchanged lifecycle counts after reads. Four final cancelled-chain/
active-unknown captures individually inspected: institution dates and wrapped proofs
are readable. Backend services/schema unchanged (heada017d865bb4c); no persistent
migration, provider, physical/load/production or whole-project acceptance claimed.

Next: native explicit activation/revision/cancellation pinned to verified root,
target and predecessor with protected same-key recovery; then current selected-version
matching and whole-waitlist detection policy/source review. All three Phase15 gates
remain OPEN and full26-phase goal stays active.


## 15K protected native lifecycle transitions

Explicit history selection freshly rereads the chosen original and causal state;
replacement selection verifies the same customer and a different current target.
Management receives focus and scrolls into view. Activation, revision and cancellation
require an explicit reason; cancelled state exposes no action. Scope, token, role,
timezone, unmount and request guards suppress late proof or writes. Histories clear
after verified confirmation and require explicit reread.

The protected driver retains the complete root/target/previous-state selection and
exact nine-field request before I/O. Key-first recovery permits POST only on literal
null. Full raw SHA and actor/request/source bindings, independent key/ID agreement,
and a freshly verified state with the complete frozen predecessor prefix and receipt
at the expected causal position are mandatory before cleanup. Later valid actions may
exist: the UI distinguishes the retained receipt from the latest state. Unknown
acknowledgement locks the decision across reload. Only definitive POST400/404/422
permits correction after a fresh null-key read; confirmation/read errors never do.
Correction clears the review and requires explicit fresh selection and reason.
Invalid local shape/hash, changed storage, quota failure and authority changes refuse
or retain safely. Shared same-storage flight locking is not cross-tab serialization;
backend optimistic version/idempotency/source authority remains unchanged.

Ten protocol and five component tests exercise all actions, lost acknowledgement,
later-state recovery, causal/actor/source tamper, definitive correction, unknown/read
errors, storage and authority races. Initial component failure was premature test
synchronization, fixed before17 focused tests passed4.70s. Initial useRef TypeScript
argument failure corrected; production build passed179 modules. Initial full frontend
445 passed109.32s, terminalexit0. Final after-focus focused15 passed9.13s, terminalexit0;
final complete frontend TAP summary445 passed97.21s, no failures/skips/cancellations,
recovered after interruption; final shell exit was not recaptured.

Initial native webserver60s startup timeout ran no UI tests and cleaned its owned
fixture; isolated rerun2 passed44.2s. Final freshly rebuilt signed Edge desktop/touch
landscape tablet2 passed1.5m (18.3s/15.6s), terminalexit0, owned temporary DB removed.
API fixtures create customer and originals; native UI performs activation, committed
lost-ack revision, reload/four-read recovery without another revision POST, stale
cancellation rejection, correction requiring explicit reread and fresh cancellation.
A second API client with the same actor advances the chain between revision and
cancellation; this is not a second native human. Four UI POSTs/profile include one
rejected stale cancellation; four retained chain events include the API peer revision.
No booking or contact occurs. Focus,44px targets,width>=600 and no overflow checked;
six final frozen/recovered/cancelled captures individually inspected and readable.
Backend/schema unchanged (heada017d865bb4c); no persistent migration, production,
physical/provider/load or whole-project acceptance claim. All three gates remain
OPEN. Next: native selected-version matching and whole-waitlist detection policies,
current source evidence and invalidation.


## 15L current matching and detection browser contracts

The browser contract binds a current read to the exact selected full-SHA causal
state, explicit channel/history/permission policy and aware horizon. Exact nested
contracts validate capture clocks, service/customer scope, duration, employee skills
and ordered windows, distinct known resource units and reservation intervals,
customer blockers, queue count partitions and retained care/permission consistency.
Policy refusal precedence and captured unknown-condition refusal cannot become
options. Proposed alternatives require exact elapsed duration, fit inside customer
and employee windows, qualifications and complete distinct resource coverage. Unit
coverage verifies the displayed assignment; it does not calculate another slot or
replace the existing backend allocator. Proposed options remain independent,
conditional and subject to revalidation before any booking or contact.

Detection checks a shared capture/policy/horizon,20-row paging, whole-cohort count
and reason partitions, sorted unique roots, cross-root unique event IDs/keys, and
returned option/reason bounds. A completely returned cohort must agree exactly;
whole off-page SQL/source verification remains15E backend authority. Capacity row
references and CRM permission originals have no new cryptographic source signature.
These contracts provide consistency checks, not browser authentication, SQL-admin
authenticity, complete real care history, physical capacity or contact authorization.

The pure typed DTO generator uses the actual deterministic domain.match kernel,
without SQL/application startup. Nine read variants cover options requiring two
distinct resources, observed care/current granted permission, cancelled/missing
registration, explicit history/permission refusal, changed duration and known/unknown
queue projection. Four detection vectors include25 active roots and20/5/empty pages,
with complete retained original/event fingerprints. Seven focused tests passed0.75s,
terminalexit0, including source/skill/resource/interval tamper, wrong version/policy/
horizon, false grant/refusal, malformed fields, queue contradictions and paging/count
corruption. Initial TypeScript boundary cast omission corrected; final production
build passed179 modules, terminalexit0. Full frontend452 passed115.83s, zero failures/skips/cancellations, terminalexit0.

No UI change or new native validation claim in15L. Prior15K native evidence retains
its original scope. Backend runtime/schema unchanged (heada017d865bb4c); no persistent
migration/provider/deployment. All three gates remain OPEN. Next: native explicit
manager policy/horizon selection, selected-version matching, whole-waitlist detection,
source/refusal inspection and invalidation with actual signed desktop/tablet tests.


## 15M native current matching and detection review

Manager Pilotage now offers explicit empty horizon/channel/history/permission
choices, using institution civil time. Missing/invalid zone blocks new reads;
skipped hours refuse and repeated hours require an occurrence that resets on edits.
Active lifecycle history selection validates the full SHA/causal state locally,
focuses and scrolls the review without HTTP. Matching sends the exact selected
latest event ID and full fingerprint; stale versions refuse and require explicit
state reread. Confirmed retained declarations/actions clear the review. No mount
read, automatic source refresh, booking, reservation or contact is performed.

Cards expose institution dates, declared/current duration, employee labels, distinct
resource IDs, conditional alternatives and explicit constraint/source/policy refusals.
Recorded care and diagnostics, absent/future/current permission on the chosen channel
and projected/unknown queue counts stay visible; unknown never becomes a grant or
free capacity. Folded proof contains the full selected version/current capture.
Opening hours and contact authority remain unverified. Detection counts lists,
not customers or jointly reserved capacity, and pages20 fresh whole-cohort reads.
Any edit/new selection/pending/error clears old results; request/unmount/scope/
timezone/token/role guards suppress late publication and old-session requests.

Five component tests plus matching contracts/lifecycle writer17 passed5.21s;
strengthened pending-unmount test then final17 passed11.69s, zero failures/skips,
terminalexit0. Initial ES2021 array.at build failure corrected by indexed access.
Full frontend457 passed93.91s, zero failures/skips/cancellations, terminalexit0. Final TypeScript/Vite production build passed181 modules, terminalexit0.

Initial native2 failed before matching: first-page search raced the read and select
labels included option text. Two correction attempts (wrong cwd/path, then ASCII
PowerShell Unicode replacement) were intentionally stopped using verified owned
Playwright trees; harness-owned temporary database cleanup completed, no successful
claim. Direct Unicode-safe patch verifies role-prefix selects and page-range waits.
Final freshly rebuilt signed Edge desktop/touch landscape tablet2 passed1.2m
(18.7s/25.4s), terminalexit0, owned temporary DB removed. API originals/activation,
CRM permission declarations and same-actor concurrent revision are fixture setup,
not new native authoring. Actual native reads verify explicit horizon/version/full
fingerprint, conditional options, absent agreement refusal, current agreement,
current refusal, stale-version400 mask/reread/new predecessor, tampered-read mask,
25 then50 active roots with20/5 and20/20/10 unique pages, focus,44px/width>=600 and
no overflow; zero UI waitlist POST. Eight final option/absent-refusal/current-refusal/
detection-card captures individually inspected and readable. Native resource-unit,
observed-care and projected-queue coverage is not claimed; existing backend15D-F
and browser contracts/DOM15L provide those dimensions' distinct evidence.

Backend runtime/schema unchanged (heada017d865bb4c); no persistent migration,
provider/deployment or whole-project/physical/load/production acceptance claim.
All three Phase15 gates remain OPEN pending canonical acceptance audit and fresh
combined regressions. Next: complete Phase15 backend SQLite/PostgreSQL and all five
native waitlist specs, requirement-by-requirement audit, then Phase16 optimizer.
