# Marketing dispatch preparation

The current implementation prepares one durable transport intent for an owned
customer and approved campaign revision. It performs no provider I/O and does not
mark the campaign SEND or establish recipient delivery. Internal worker execution
and trusted outcome retention are implemented with injected adapters. Opt-in API
adapters are available; deployed invocation, live acceptance and delivery-event
verification remain. See [transport contracts](MARKETING_TRANSPORTS.md).

`MARKETING_ACCOUNTS_JSON` is a server-side account allowlist, empty by default.
Each entry is an exact `Account` with `institute_id`, `provider`, `account_id`,
`channel` (`email`, `sms`, `push`), `sender_id`, `mode` (`live`, `test`) and
`push_application` (required for Push, null otherwise). Duplicate account IDs
within an institute/channel invalidate the configuration. Keep credentials out
of this list. Listing an account permits preparation only; it does not configure
a transport adapter or prove provider/account ownership. Test mode facts cannot
be treated as live acceptance.

A signed institute manager can POST `/api/v1/marketing/institutes/{institute_id}/dispatch-intents`
with `campaign_id`, `expected_revision_id`, `customer_id`, `expected_contact_id`,
`account_id`, `reason` and `idempotency_key`. Actor comes from the signed session.
The service locks the institute, resolves an existing key first, then for a new
intent requires the exact retained approval selected by expected_revision_id and
current contact. The campaign must currently be that APPROVE or its direct SEND
successor, with a nonfuture current stage. It requires an approved retained
customer, granted permission and declared channel destination at one aware clock.
Push application must match the server account. Current approval does not override
a withdrawal. There can be only one intent for a revision/customer; recovery must
use its original key rather than creating a new operation.

The receipt retains full transport terms, source originals, signed actor and a
canonical SHA-256 fingerprint. GET `dispatch-intents/original/{key}` and
`dispatch-intents/{identifier}` independently reread the owned original and its
historical campaign/contact sources. An identical request and actor can recover
the original after current sources or account configuration change. Historical
recovery does not authorize a later send: execution must recheck current sources
and account configuration before its first submission. An uncertain prior attempt
must be reconciled under the same stored operation key.

The schema migration `3fa0c198447b` adds intents, outcome originals and current
outcome pointers. Source/owner, replay and one-recipient constraints are enforced
in SQL. JSON semantics, APPROVE stage and current-source authority are enforced
by services. Any retained dispatch history blocks downgrade, including an intent
without a result. Offline downgrade cannot verify history and is refused. No
production migration or live provider acceptance is implied by repository tests.

The internal `dispatch_outcomes.append` entry point accepts trusted adapter
observations only. It validates the stored intent account/key/fingerprint, exact
current outcome predecessor, nonfuture retention and monotonic observation clocks.
An unknown result can be followed by another unknown or a terminal acceptance or
rejection; a known provider message reference cannot change. Terminal submission
outcomes cannot be replaced. Delivery events require separate evidence and cannot
be recorded as submission acceptance. Original-key recovery checks complete terms
and worker actor before consulting the current outcome or clock.

Managers can GET `dispatch-intents/{intent_id}/outcomes` with bounded `offset` and
`limit` (default 20, maximum 50), plus `outcomes/current`, `outcomes/original/{key}`
and `outcomes/{identifier}`. These routes cannot write provider results. The page
is an ordered bounded audit, not proof of the full predecessor chain outside the
page. Present predecessor cycles and incoherent predecessor transitions refuse.

`dispatch_worker.run` is an internal entry point requiring a session factory,
owned intent, exact worker actor and trusted local account-to-adapter resolver.
There is no public execution endpoint or automatically activated daemon. For the
first decision, the worker checks current full campaign/contact/registration and
current configured account under the institute lock. It commits an unknown outcome
before any provider call and then releases the database transaction. The adapter
must bind the exact configured account; resolver lookup must perform no network I/O.

The committed decision is the ordering point for concurrent source corrections.
Provider I/O runs outside the institute lock so operational mutations can continue.
A withdrawal before that decision prevents submission; a later withdrawal cannot
retract an already decided request or erase an uncertain previous attempt. Every
existing unknown outcome uses reconciliation only, with unchanged original key,
destination and approved content. Terminal observations return without provider I/O.
Account removal/change blocks further provider calls; historical receipts remain.

Timeouts and invalid/mismatched responses leave the durable unknown. A persistence
failure after provider acceptance also leaves the committed decision recoverable.
A crash after committing the decision but before calling submit likewise resumes
with reconciliation only: if the provider cannot establish an outcome, the intent
remains unknown. The worker never fabricates rejection or automatically submits
again to resolve this ambiguity. Deployed adapters and operator resolution still
need acceptance. Missing current pointers with retained history refuse submission.

## Signed SEND declaration and first-attempt gate

The existing manager-only campaign POST now accepts action `send` with the exact
current approved revision, null content, explicit reason and operation key. It
retains a new SEND original/head atomically, with unchanged content and approval
and review digests. Read-by-key/ID/current/audit/catalog validate its owned APPROVE
predecessor. Full actor/terms replay precedes current head and clock; competing
keys cannot both append. Editing or repeating SEND as a new action is refused.
SEND records the manager declaration, not recipient delivery or a provider call;
revision delivery/external-message flags remain false.

A first worker decision now requires that current SEND directly follows the exact
approval saved in the intent, is no later than the decision clock, and retains the
same content. It reevaluates the saved approved campaign against current exact
contact/registration and configured account. APPROVE alone creates no outcome or
provider attempt. An already uncertain attempt still reconciles only, independently
of subsequent source corrections; terminal results remain read-only.

Recipient intents can be prepared while APPROVE is current or after its direct
SEND successor. expected_revision_id always names the retained APPROVE, not the
SEND revision; submissions keep that approval and the fresh contact originals.
The SEND head must be nonfuture, and permissions/destination/configuration are
reevaluated during preparation. A foreign or replaced approval refuses; one
intent per approval/customer and full-key historical recovery remain unchanged.

The manager can now choose Autoriser l'envoi from a verified approved campaign,
with an explicit reason. The request is retained per institute/actor/campaign
before POST. Recovery reads by key/ID/current and independently reads the exact
APPROVE predecessor, stage, digest and chronology before clearing protected terms.
A lost reply/reload recovers without another POST; corrupted approval keeps the
request frozen. Native SEND performs no provider I/O. New corrections are disabled
there, while protected old-request recovery remains. Native recipient intent/result
workflow and deployed sending acceptance
remain to be completed.

## Current recipient observations after SEND

The owned bounded recipient page now accepts current SEND as an approved stage.
It still pins the exact current revision and retained membership order, one aware
observation clock, current contact original and explicit channel grant/destination.
SEND does not override withdrawal, unknown permission, missing destination or
future source clocks. Backend SEND receipt validation retains the approved
predecessor; an old approval ID cannot stand in for the current SEND observation.
The frontend recomputes the same reasons and independently rereads campaign and
contact originals. Forged eligibility hides the whole page until a clean reread.

These observations declare current eligibility only. Whole-campaign evaluation,
provider submission and delivery flags remain false; native intent preparation,
provider outcome audit and deployed execution remain separate pending work.

## Owned dispatch selection catalogs

Manager-only GET `dispatch-accounts?channel=email` (or sms/push) returns bounded
server Account metadata for the signed institute/channel. Offset defaults to zero,
limit to 20 (maximum 50); total and exact page length agree. Entries are ordered by
account_id. The same strict complete allowlist parser serves preparation and worker
lookup: invalid/ambiguous entries refuse, extra inline credential fields refuse,
and error context is suppressed. No credential-binding environment references or
provider connection secrets are returned. An account listed here does not prove
credential availability, provider ownership or deployed execution readiness.

GET `campaigns/{campaign_id}/dispatch-intents` returns bounded historical intent
originals across all retained approvals of the owned campaign, ordered by retained
created_at and ID. Every returned original revalidates its submission fingerprint
and independently retained campaign/contact sources. Changed current campaign or
account configuration does not rewrite historical originals. A corrupt original
refuses the page; bounded reads do not validate history outside their page. Existing
key/ID and outcome current/key/ID/audit reads support subsequent independent native
verification. These intent originals include declared recipient contact facts and
remain manager-only, with no provider connection credentials. Neither catalog
performs submission, reconciliation, outcome mutation or live account acceptance.

## Native dispatch contracts

`marketing-dispatch-utils.ts` validates exact Account metadata and bounded account/
intent/outcome pages, retained approved Submission sources, requests, intent receipts
and submission results. The intent fingerprint matches backend Python SHA-256:
UTC-normalized aware timestamps with microseconds, sorted object keys, ASCII JSON
Unicode escapes and original array order. Nonselected channel contact facts remain
part of the fingerprint. Valid shapes/fingerprints do not authenticate an API response
or establish current dispatch authority; consumers must independently reread originals.

Receipt matching separately pins the signed actor, full request and selected Account
metadata, including provider/mode/sender/application. Unknown/accepted/rejected
observations bind the exact intent/account/key/fingerprint; acceptance needs a provider
reference and delivery_confirmed remains strictly false. Outcome retention/observation
clocks are checked. Bounded audit validates present predecessor cycles, terminal
successors, monotonic clocks and stable known references; it makes no claim about
predecessors outside the page.

The checked-in three-channel JSON vectors come from the explicit isolated SQLite
exporter `backend/tests/export_marketing_dispatch_13ar.py`: actual retained service
intent/approval/contact/catalog/outcome originals, test-mode fixture accounts and
simulated internal observations, never provider I/O. Native tests use these backend
fingerprints, offset-equivalent clocks, Unicode and deliberate corruption. The native
preparation/recovery/outcome reader components remain to be connected; these helpers
do not read storage, prepare intents, invoke workers or display live acceptance.
