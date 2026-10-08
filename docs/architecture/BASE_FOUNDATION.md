# BASE foundation — Phase17

Authority: Master Plan sections8/11/12/13/38, architecture foundations and accepted
ADRs003/004. BASE orchestrates authorized intentions through existing application
services; official business facts remain deterministic domain output. The full
26-phase objective stays ACTIVE. All six Phase17 gates remain OPEN.

##17A closed read/suggest capability foundation

`app/modules/base/read_capabilities.py` registers exactly three real service
adapters, not arbitrary tools or unimplemented mutation placeholders:

| Capability | Trust level | Existing application authority | Selection required |
| --- | --- | --- | --- |
| WAITLIST_READ |0 READ | `waitlist.lifecycle.read_state` | Explicit retained root ID |
| WAITLIST_MATCH |1 SUGGEST | `waitlist.sources.read` | Root/latest event ID/full SHA, aware horizon, explicit existing matching policy |
| PLANNING_OPTIMIZATION |1 SUGGEST | `optimizer.sources.read` | Selected retained policy ID/full SHA plus matching selection |

The immutable registry records permitted roles, exact institute context, service
identity, non-mutation/non-external effect and no required approval for these
read/suggest-only operations. Discovery returns only capabilities permitted for
the principal in the exact requested institute. Existing services are manager-only,
so the registry does not widen them to reception/collaborator/direction/admin.
Other examples in Master Plan section13 remain unregistered until their actual
service adapter, permissions, business guards and action lifecycle are implemented.
No execution capability is inferred from a tool name or natural-language request.

Principal construction must use server-decoded JWT claims; no HTTP body/provider
may supply actor, role or institute authority. Exact actor/institute/known role are
validated and revalidated before dispatch, including unsafe typed-model copies.
The structured discriminated invocation rejects unknown capabilities, additional
identity/approval/level fields, generated SQL and dynamic callable names. Its
envelope is a frozen extra-forbidden model; nested arguments retain their original
strict source/rule/aware-horizon validators. The shared Fact wildcard before-
validator is intentionally excluded from the literal capability discriminator.

Context contains only authorized principal, registered capability and explicit
selected arguments. It is labelled `authorized_selection_not_captured_business_facts`;
it does not pretend that IDs/hypotheses are observed capacity or a customer summary.
Invocation uses explicit code dispatch, never import/eval/generated SQL. Existing
service ownership, causal version, policy fingerprint, current capacity/history/
permission and source integrity guards run unchanged. The wrapper preserves their
typed result and refusal. It adds a server read-completion timestamp (not a shared
business capture) and explicit read/suggestion-only effect; source clocks remain
untouched. No new booking, contact, global policy activation or LLM score runs.

The signed API now exposes capability discovery, selection-context resolution
and registered reads under `/base/institutes/{institute_id}`. Server authentication
constructs the principal; bodies cannot supply actor, institute, role or approval.
Context resolution does not load business data or prove ownership of selected
IDs. Actual reads run the existing service ownership and current-source guards.
The response wraps the complete evidence with its full SHA256, explicitly labelled
as response integrity rather than retention or a signature. Reception can discover
an empty registry, but cannot resolve or invoke manager capabilities; other roles
and foreign institutes are rejected at the signed entrypoint.

At17B the foundation added no frontend, migration, provider call or persisted BASE
interaction audit. `resolve` validates a structured candidate; it is not completion of
the canonical natural-language Intent Resolver. The selected context/evidence
types likewise do not complete every Context/Evidence/Audit/Planner/Approval
requirement. Sensitive LEVEL3 orchestration still requires the relevant permission,
domain validation, explicit human approval, audit and idempotent workflow.

##17C language proposal and explicit selection boundary

`POST /base/institutes/{institute_id}/intents/resolve` accepts a bounded nonempty
utterance and at most20 distinct, strictly typed explicit selections. Signed scope
and selection permissions are verified before interpretation. The internal
provider-neutral `Interpreter` receives only the utterance and permitted capability
names; selected arguments, server identity and database handles are not supplied.
The utterance itself may contain personal data, so this interface is not a claim
of anonymization. No external provider is currently called.

The local implementation recognizes conservative whole-utterance French/English
phrases for the three registered capabilities, including polite prefixes and accent,
apostrophe and terminal-punctuation normalization. Unrecognized language requires
clarification. This is a bounded grammar, not general natural-language coverage;
the provider layer and broader language UX remain later work. Negated, mixed and
instruction-injection examples cannot match by substring. A future provider can
propose only a known capability or clarification/unsupported outcome, never an
actor, role, argument, approval or executable operation. Malformed output and
provider failure reject with502 without local fallback or leaking diagnostics.
Fake interpreter tests exercise this boundary without vendor SDKs.

A recognized capability becomes `ready` only with exactly one matching explicit
selection. Missing selection or multiple references require clarification; other
selected capabilities cannot win by ordering. The returned invocation preserves
validated source references, fingerprints, aware horizon and explicit policy.
Resolution loads no business data and executes nothing. `ready` is neither human
approval nor business eligibility: context is still only an authorized selection.
Source ownership, freshness and business guards run when a subsequent registered
read is explicitly requested. The hash covers the canonical typed request, not a
signature, retained interaction, semantic proof or cross-actor authority.

##17D retained preparation and history

Signed manager endpoints create `/plans`, recover `/plan-by-key`, read one plan
and page plan history. Explicit preparation resolves the supplied bounded language
request, requires a unique explicit selected operation, then captures existing
read/suggest service evidence under the institute lock. It retains raw utterance,
selected arguments, reason, signed actor/institute, resolution, complete delegated
result and server completion/creation clocks. This is preparation of one registered
operation, not a general multi-step planner, LEVEL3 capability or human approval.
Service refusals are retained as refusals; stale sources reject before insertion.
No booking, contact or external action runs. Preparation explicitly performs a
business read, unlike the earlier intent/context endpoints.

Recovery keys bind the exact typed request and original actor. Same-key replay
returns the old verified capture without business reread; changed terms or actor
refuse. Historical interpretation is retained, not recomputed from a future
language provider. Verification checks full raw SHA, canonical typed snapshot,
column/clock/actor binding, exact selection/context/result type, owned root,
matching horizon/rules/causal head and selected scoring policy. These are retained
consistency proofs, not cryptographic signatures or new source calculations.
History verifies the whole institute cohort before slicing20-row pages, including
off-page corruption. Reads of retained plans do not certify current eligibility.

Migration `c239f071bad3` follows `b128ef60a9d2`; it adds only the scoped replay-unique
`base_plan_originals` history table. Online empty downgrade is possible; retained
rows and offline downgrade are guarded. Deployment requires applying this migration
through the existing controlled procedure. The persistent application DB is not
migrated by development verification. This history covers successful preparations,
including delegated refusals; unresolved/rejected intents and other BASE reads are
not yet a complete interaction audit. Approval lifecycle, multi-step planning,
secured execution adapters, broader language and native UX remain required.

##17E sensitive cancellation preflight and transaction boundary

An independent closed sensitive registry exposes APPOINTMENT_CANCEL preparation
metadata (LEVEL2, future LEVEL3, exact manager scope, explicit approval of a retained
operation required). `GET /sensitive-capabilities` and explicit
`POST /sensitive-previews/appointment-cancel` are signed manager-only. This is not
an execution endpoint, an approval, or an extension of the read/suggest invocation
union. Read/intention/read-plan requests still reject APPOINTMENT_CANCEL.

The preview scopes the selected appointment query to the signed institute under
the existing institute lock. It delegates status and owned-employee eligibility
to shared appointment service guards. Known scheduled/confirmed/arrived appointments
are cancellable; final/in-progress/unknown status or missing/foreign employee
refuse. Employee ownership is fetched fresh with the institute predicate, so a
stale identity-map value cannot authorize another institute's staff modification.
The preview captures only existing operational booking snapshot fields and count/
full hash of the complete currently recorded booking-event cohort. Names, phones
and free-text notes are not exposed; customer IDs remain personal references,
not anonymized data. Future recorded events refuse. The state hash covers scope,
target, snapshot and history: a later event invalidates it even when the visible
operational snapshot returns to its earlier value. It is not a signed token,
retained approval or proof of complete real-world history/current future eligibility.

The existing `cancel_appointment` service now accepts internal keyword-only
`commit=False` for a caller-owned transaction. It still applies the same business
guard, releases reservations, synchronizes the owned employee and writes the
existing booking event. The default remains commit/refresh for current manual
routes; non-boolean transaction mode refuses before reading. Caller-owned mode
flushes without committing, allowing later BASE decision/execution receipt to be
atomic with the business operation. No HTTP body controls this mode. This is a
transaction prerequisite, not an implemented approval/execution orchestrator.
No new schema, provider call, native UI, retained sensitive operation or approval
is introduced here. Next work must retain the exact operation, obtain human
approval, revalidate current eligibility and execute through this service with
scoped idempotent audit; metadata alone never grants execution.

##17F retained pending sensitive operations

Signed manager `/sensitive-operations` create/history/detail and
`/sensitive-operation-by-key` recovery retain APPOINTMENT_CANCEL preparations.
The request supplies only the explicit selected appointment, reviewed state SHA,
reason, recovery key and explicit aware `valid_until`. Validity is normalized to
UTC, with no invented deadline. Preparation locks the institute, rereads the
current owned preview and refuses changed state or already elapsed validity.
It stores signed actor/institute, exact request, complete canonical operational
snapshot/history hash, server capture/creation clocks and full retained SHA.
The immutable original effect is pending human approval and no execution; it is
not a mutable approval state, even after a future decision.

Preview snapshots now validate a complete closed typed operational shape,
cancellable status, positive interval and UTC instants before state hashing.
Typed snapshots use canonical JSON UTC `Z`; older unretained preview hashes may
therefore require explicit reread. No earlier stored sensitive original exists
to migrate; retained read/suggest plans are unaffected. Preview verification
checks manager authority, registry metadata and the full state-hash binding.
Retained verification checks raw full SHA, exact canonical typed snapshot,
request/preview/actor/institute/appointment/hash binding, columns and
capture <= creation < explicit validity. It never recaptures current state to
interpret historical evidence. Hashes are consistency checks, not signatures.

Same-key replay returns the original verified operation without rereading or
changing validity. Different terms or actor refuse. Expired originals remain
recoverable historical records; expiry must prohibit future approval/execution,
not erase history or cause a duplicate preparation. History verifies the complete
owned cohort before20-row pages, including corruption outside the requested page.
The recorded customer IDs and staff references are personal data under institute
manager access; this is not anonymized evidence or complete interaction audit.

Migration `d340a182cbe4` follows `c239f071bad3` and adds only scoped, replay-unique
`base_sensitive_operation_originals` and its history index. Offline downgrade and
any downgrade deleting retained rows refuse. Persistent application migration is
not performed by these owned validation fixtures. Human approve/decline/revoke,
current-version revalidation and atomic idempotent execution/audit remain the next
required work. No public executor, provider call or native UI is added here.

##17G explicit approval decision lifecycle

Signed manager `POST /approvals` accepts only operation ID/full retained SHA,
paired previous decision ID/full SHA, explicit approve/decline/revoke, reason and
recovery key. Actor and creation/source clocks are server supplied. Approval
requires a pending, unexpired operation and an actual reread of the owned current
appointment through the existing preflight; its state SHA must still match the
prepared version. The retained decision records that verified SHA and source
check clock. A pending operation can instead be declined without recapturing
business eligibility. An approved operation can be revoked, including after
expiry or source change. Declined/revoked chains are terminal; a new operation
must be prepared for reconsideration. The preparing and deciding manager may
be different; no unstated four-eyes restriction is invented.

`GET /approval-by-key` and `/sensitive-operations/{id}/approval-state` verify the
entire operation decision chain. Raw SHA, canonical snapshot, columns, actor,
UTC clocks, operation full SHA, exact predecessor/full SHA, chronological order,
transition and original source/validity binding are checked. Branches, cycles,
disconnected or corrupt later decisions refuse even recovery of an earlier row.
The institute lock serializes initial decisions (including SQL NULL predecessors)
and subsequent decisions; replay and successor uniqueness constraints supplement
the application causal guard. Replaying an approval after revocation returns its
historical receipt without reinstating approval or reading business sources.
Changed key terms/actor refuse. Full state reads show expiry separately from the
retained human decision and explicitly do not revalidate current business sources.
An `approved` history status is therefore not sufficient execution authority.

These are explicit signed decision requests, not evidence of physical human input
in a native UI; the native review/approval experience remains required. No language
provider receives approval authority. Decisions never call cancellation or any
external executor. The prepared original stays immutable and still describes its
preparation effect; current approval status comes only from the verified chain.

Migration `e451b293dcf5` follows `d340a182cbe4`; it adds scoped key-unique causal
`base_approval_originals`, operation/self-predecessor FKs and history index. Empty
online downgrade is allowed, retained decisions and offline downgrade refuse.
Persistent application migration is not performed. Next execution must verify
the latest approved predecessor, original validity and fresh source again, then
commit service effects and its own idempotent receipt together. Complete BASE
interaction audit, broader adapters/planning/language and native UX remain open.

##17H atomic approved cancellation execution

An independent immutable execution registry and signed manager
`GET /execution-capabilities` describe the implemented APPOINTMENT_CANCEL LEVEL3
adapter. Preparation descriptors remain historical preparation metadata, including
their original `public_execution=false`; they are not retroactively changed to
execution entitlements. Read/intent/read-plan unions remain closed to cancellation.
Explicit `POST /executions` accepts only operation ID/full SHA, approval ID/full
SHA, reason and recovery key. It requires the latest approved chain, unexpired
operation, exact references and actual current preflight state matching the
prepared SHA under the institute lock. It then calls the existing cancellation
service with caller-owned commit, captures its operational result and the one
new existing booking event, writes the execution original, verifies all proofs
and commits them together. Validity is checked again before confirmation.
Recorded appointment instants and booking-event capture timestamps are normalized
to UTC before hashing, so a PostgreSQL connection timezone does not change the
reviewed version or execution event proof. Existing raw event JSON stays intact.
No provider explanation, generated SQL, inferred approval, contact or refund runs.

Execution key/actor/typed terms bind exact replay; operation uniqueness prevents
another key from executing it again. `GET /execution-by-key` and
`/sensitive-operations/{id}/execution` verify original full SHA/canonical columns,
signed actor/scope, before/after effect, approved operation/decision/validity and
the actual owned booking-event full SHA, actor, clock and snapshots. Historical
replay performs no source recapture or mutation, including after original expiry.
Corrupt receipts or booking-event evidence fail closed. Event/receipt timestamps
and consistent snapshots are proof of recorded effects, not cryptographic
signatures or complete external/physical history. No private customer text is
included in the operational snapshot; declared reasons still belong to the audit.

Any error after cancellation but before commit rolls back appointment, employee,
resource reservations, booking event and receipt in the same SQL transaction.
Committed lost acknowledgement recovers by the exact key. Concurrent callers use
the same institute lock as approval/revocation and booking changes. A new approval
decision after recorded execution refuses: revocation cannot undo a performed
cancellation. Historical approval replay remains available. Approval state itself
does not claim to execute; clients must inspect the separate execution receipt.

Migration `f562c3a4edf6` follows `e451b293dcf5`, adds scoped key-unique and
operation-unique `base_execution_originals` with operation/approval/booking-event
FKs, and refuses offline or populated downgrade. Persistent application migration
is not performed. Native explicit human review/decision/execution and broader
operations/full interaction audit remain required; this is backend functional
execution verified on owned fixtures, not real customer/production execution.

## Evidence and remaining work

Initial six-module test collection failed because inherited wildcard before-
validation is incompatible with Pydantic's literal discriminator; invocation
envelope was isolated without weakening nested argument guards. Final complete
six-module **58 passed81.72s**, zero failures/skips, terminalexit0, SQLite and
actual isolated PostgreSQL. Eleven BASE cases cover closed immutable discovery,
known-role/exact signed scope, unknown/mutating/dynamic/SQL/client-identity
injection, unsafe model copies, actual delegated reads/matching/scoring, preserved
permission refusal/stale fingerprint, repeated results and unchanged original
row counts. Existing optimizer current sources/originals/normalization/kernel
regressions also pass. Existing crypt and intentional unsafe-copy warnings only.
No native/whole-project/production acceptance claim; headb128ef60a9d2 and persistent
application/provider/deployment state are unchanged.

Phase17B adds three signed HTTP test cases to the existing service regressions:
seven modules **61 passed187.73s**, zero failures/skips, SQLite and actual isolated
PostgreSQL. HTTP tests use isolated SQLite; no live PostgreSQL HTTP claim is made.
They cover discovery, context without business reads, complete response SHA,
server actor, forbidden roles/foreign scope, identity/SQL/unknown-tool injection,
preserved source refusal/stale fingerprints and unchanged original counts. Schema
head and persistent application/provider/deployment state remain unchanged.

Phase17C final four-module suite **52 passed25.00s**, zero failures/skips,
terminalexit0, SQLite and actual isolated PostgreSQL. Thirty-three new intent
cases cover supported French/English formulations, negated/mixed/injected unknown
language, missing/multiple/duplicate references, provider minimization and strict
output, failures without fallback, unsafe copies, signed HTTP roles/scope/identity,
input limits and all three current selections without business reads. HTTP remains
SQLite; PostgreSQL coverage is existing delegated-service regression evidence.
Initial run1 failed/43 passed/1 skipped35.73s exposed punctuation whitespace and
omitted PostgreSQL environment. Corrected run51 passed24.76s; adding the all-three
HTTP case exposed a fixture assertion comparing equivalent UTC spellings
(1 failed/51 passed101.63s). Expected values now use the existing typed canonical
serialization; no business/time validator was weakened. Existing crypt and
intentional unsafe-copy serializer warnings only. No native/frontend/general
language/live-provider/whole-project acceptance claim.

Phase17D final eight-module suite **71 passed77.92s**, zero failures/skips,
terminalexit0, SQLite and actual isolated PostgreSQL. Six new plan cases verify
retention/replay/no recapture, changed actor/terms refusal,25-row paging and
off-page/rehashed selection/nested-reference corruption, signed HTTP roles/identity,
current matching/scoring and preserved permission refusal/stale-source rejection,
real PostgreSQL same-key/conflicting-key races and flush rollback/committed lost-ack
recovery. Three new migration cases prove offline guard and owned SQLite/PostgreSQL
empty roundtrip, metadata parity and populated downgrade refusal. Existing intent,
BASE routes/services and optimizer current/original/migration regressions pass.
Initial four-module50 passed21.98s; expanding snapshot validation initially caused
an indentation import error (exit4, no cases run), corrected before eight-module
68 passed146.21s. Added nested SHA and race/recovery checks then final71 passed.
Only existing crypt/intentional unsafe-copy warnings. HTTP remains SQLite; no
native/frontend/whole-project/production acceptance claim. Persistent application
schema remains untouched; new deployment prerequisite is headc239f071bad3.

Phase17E final nine-module suite **75 passed90.89s**, zero failures/skips,
terminalexit0, SQLite and actual isolated PostgreSQL. Fourteen new cases cover
all eight status cases, signed/scoped strict preview and closed discovery,
no mutation/no private-text exposure, same-snapshot event invalidation,
caller-owned rollback/commit including reservations and booking audit, unsafe
selection/non-boolean transaction-mode refusal and real stale-identity-map
ownership changes on both databases. Existing booking confirmation/move/resource
lifecycle and BASE plan/intent/route/service regressions pass. Initial six-module
1 failed/25 passed88.66s came from assuming a second demo institute; owned foreign
fixture added. Scope/status guards then nine-module73 passed51.43s; fresh scoped
employee query and two cache tests added before final75 passed. Existing crypt
and intentional unsafe-copy warnings only. HTTP is SQLite; no native/frontend/
whole-project/production claim. Schema headc239f071bad3 unchanged, persistent
application/provider/deployment untouched; no new migration or public executor.

Phase17F final eight-module suite **79 passed125.34s**, zero failures/skips,
terminalexit0, SQLite and actual isolated PostgreSQL. Six new retained-operation
cases verify25-row history/recovery, expired replay without recapture, equivalent
aware validity normalization, changed actor/terms refusal, raw/rehashed off-page
snapshot/actor/validity/count corruption, signed HTTP role/scope/injection,
stale reviewed version and expired new request rejection, actual same-key and
conflicting-key races, flush rollback and committed lost-ack recovery. Three
migration cases cover offline guard, owned SQLite/PostgreSQL empty roundtrip,
metadata parity and populated downgrade refusal. Existing preflight, retained
read plans/migration, intent and signed BASE route/service regressions pass.
Initial three-module26 passed35.91s; UTC normalization/canonical snapshot checks
and migrations were added before final79 passed. Existing crypt/intentional
unsafe-copy warnings only. HTTP remains SQLite; no native/frontend/whole-project/
production claim. Persistent application/provider/deployment untouched; new
controlled deployment prerequisite is headd340a182cbe4.

Phase17G final ten-module suite **89 passed122.33s**, zero failures/skips,
terminalexit0, SQLite and actual isolated PostgreSQL. Seven new approval cases
cover approve/revoke with different manager, historical replay after revocation,
terminal/stale-predecessor/changed-key/actor refusal, later-decision rehashed
corruption invalidating earlier recovery, changed/expired approval refusal and
explicit expired decline, signed HTTP scope/identity/full SHA/unknown-action
injection, actual PostgreSQL same-key and competing initial decisions, flush
rollback and committed lost-ack recovery. Three migration cases cover offline
and populated guards, owned SQLite/PostgreSQL empty roundtrip and metadata parity.
Existing sensitive preparation/preflight, retained read plans, their migrations,
intent and BASE signed routes/services regressions pass. Initial two-module
13 passed26.61s before migration/full regression expansion. Existing crypt and
intentional unsafe-copy warnings only. HTTP remains SQLite; no native physical
human-input/frontend/whole-project/production acceptance claim. Persistent
application/provider/deployment untouched; controlled deployment now requires
heade451b293dcf5.

Phase17H initial execution/approval two-module18 passed36.12s. Expanded
12-module **103 passed200.16s**, zero failures/skips, terminalexit0, SQLite and
actual isolated PostgreSQL, including three new execution migration cases and
existing BASE migrations/full regressions. Added actual execution/revocation race
and non-UTC PostgreSQL connection proof; four-module1 failed/39 passed65.15s found
that the shared SQLite metadata-restoration helper preserves aware offsets, so
history/event hash timestamps also needed explicit local UTC normalization.
Corrected only BASE snapshot/history/event normalization; shared time behavior
unchanged. Final affected four-module **40 passed110.90s**, zero failures/skips,
terminalexit0, SQLite/actual PostgreSQL. Thirteen execution cases cover exact
receipts/event tamper, replay after expiry/no recapture, changed actor/key/terms,
late revocation, pending/revoked/changed/expired/wrong-reference refusal, signed
HTTP strict scope, real competing executions and execution/revocation, rollback
of business effects when receipt flush fails, committed lost-ack/resource recovery
and non-UTC source/event proof. All affected preflight/sensitive retention/approval
regressions pass. Earlier12-module baseline is not claimed as a fresh105-case run.
Only crypt/intentional unsafe-copy warnings. HTTP is SQLite; no native physical
human-input/frontend/whole-project/production claim. Persistent app/provider/
deployment untouched; controlled migration prerequisite is headf562c3a4edf6.

Phase17I adds browser proof contracts for preview, retained operation, individual
decision, complete causal approval state and execution receipt. Exact fields,
institute/appointment/actor bindings, canonical UTC microseconds, full SHA and
validity/transition constraints are checked. Same-clock decisions follow explicit
predecessor IDs and fingerprints, not lexical ordering. Historical expiry does
not invalidate a receipt completed within the original validity interval; it
does not authorize another execution. Pending operation effect stays immutable.

Python-generated typed synthetic vectors establish cross-language canonical hash
compatibility, including Unicode. Six focused tests pass825.25ms; full frontend
493 passed84352.89ms, zero failures/skips, terminalexit0; TypeScript/Vite build
passes186 modules. Browser hashes establish internal consistency, not signatures,
SQL event existence, current source authority or physical human input. Actual
booking-event verification remains exclusively in the server execution service.
These contracts are not yet connected to native UI; no new UX acceptance claim.

Phase17J adds separate operation, decision and execution intent drivers with
institute/actor/mode-scoped storage and in-flight serialization. Strict requests
are cloned and retained before any I/O; reloads preserve those exact terms even
when the form changes. Only literal null from the matching key read permits a
POST. Ambiguous acknowledgement, corrupt storage, mismatching actor/terms/proof,
or stale context preserve the pending request. No driver automatically starts
work; callers must invoke submit explicitly and supply a live scope guard.

Confirmation verifies the response, a fresh key lookup and an independent
operation detail, full decision chain or per-operation execution receipt before
clearing storage. Decision recovery requires membership in the verified causal
chain, including historical decisions after revocation. Execution recovery also
verifies the complete approved chain; an expired state can confirm a prior valid
execution. Full server/domain event verification remains authoritative. A
definitive POST400/404/422 can offer correction, but only a fresh null key lookup
allows clearing; a now-present receipt is recovered instead. Reloads cannot
infer correction eligibility from an old failure. Cleanup failures retain the
request for another verified recovery. No native UI integration yet.
Final27 focused tests pass521.13ms; complete frontend520 passed86417.69ms,
zero failures/skips, terminalexit0; TypeScript/Vite build passes186 modules.
Initial harness failures were corrected (captured callbacks and a forged actor
equal to the fixture's real actor); no product proof was weakened. These are
browser protocol tests with typed synthetic receipts, not new database/native
physical human input or production acceptance.

Next: native human review/decision/execution, complete interaction audit, broader planning/language handling and supported
service adapters. Canonical Context Resolver, Intent Resolver, Capability Registry,
Permission Guard, Business Rule Guard, Action Planner, Approval Manager, Evidence
Builder and Audit Trail must all be verified before closing Phase17. Architecture
and existing service/action authorities are preserved; no ADR change is needed.
