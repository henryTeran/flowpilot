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

This is an internal foundation. It adds no API route, frontend, migration, provider
call or persisted BASE interaction audit. The module is not yet imported by the
API runtime. `resolve` validates a structured candidate; it is not completion of
the canonical natural-language Intent Resolver. The selected context/evidence
types likewise do not complete every Context/Evidence/Audit/Planner/Approval
requirement. Sensitive LEVEL3 orchestration still requires the relevant permission,
domain validation, explicit human approval, audit and idempotent workflow.

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

Next: signed BASE entrypoint/discovery and authorized minimal context/evidence
projection, structured intent/ambiguity handling with a provider-neutral language
boundary, followed by retained plans, approval lifecycle/audit and supported
service adapters. Canonical Context Resolver, Intent Resolver, Capability Registry,
Permission Guard, Business Rule Guard, Action Planner, Approval Manager, Evidence
Builder and Audit Trail must all be verified before closing Phase17. Architecture
and existing service/action authorities are preserved; no ADR change is needed.
