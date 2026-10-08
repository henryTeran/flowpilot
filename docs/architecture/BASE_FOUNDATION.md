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

Next: approval lifecycle, complete interaction audit, broader planning/language handling and supported
service adapters. Canonical Context Resolver, Intent Resolver, Capability Registry,
Permission Guard, Business Rule Guard, Action Planner, Approval Manager, Evidence
Builder and Audit Trail must all be verified before closing Phase17. Architecture
and existing service/action authorities are preserved; no ADR change is needed.
