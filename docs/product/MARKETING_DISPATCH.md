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
fingerprints, offset-equivalent clocks, Unicode and deliberate corruption. The native preparation/recovery component now consumes these helpers. Retained
outcome readers remain pending; the helpers themselves do not read storage, invoke
workers or display live acceptance.

## Native protected recipient preparation (13AS)

The verified recipient panel offers an explicit account selection and reason. No
account is preselected and no account/intent read runs on mount. Bounded account
pages preserve retry offsets; signed manager GET `dispatch-accounts/{id}?channel=...`
rereads the selected metadata independently. Provider, mode, sender and Push
application remain visible; a mismatched Push application blocks preparation with
an explanation. Catalog metadata does not establish live provider readiness.

Protected session storage is scoped to institute/actor/campaign/customer and holds
only full Request and selected Account metadata, never recipient destinations or
device tokens. Before a new POST, current campaign, retained approval, current
contact plus its ID/key originals and selected account must match the verified
selection. The backend remains authoritative for fresh scope/grant/clock checks.
A newly generated request that fails before any POST is cleared for correction;
older protected requests and ambiguous POST responses remain frozen for recovery.
Explicit 400/422 refusal permits deliberate correction with an exact storage match.

Recovery first reads the original operation key. It verifies full actor/request/
account/fingerprint, independent intent key/ID, historical approval/contact ID/key
and owned current campaign before clearing protected storage. A lost reply and
subsequent withdrawal recover the same retained intention without another POST;
historical recovery does not require current permission or configured account.
The verified receipt explicitly says that preparation triggers no sending. This
component neither invokes a worker nor writes an outcome.

The owned loopback browser launcher accepts the explicit test-only profile:
`npm.cmd run test:browser:backend -- --marketing-fixture marketing-dispatch-prepare.spec.ts`.
It supplies fixture-only test-mode account metadata in the owned temporary SQLite
server, including 25 email choices for pages 20/5. Default application configuration
remains empty; no credential binding, adapter or external provider is installed.

A retained intent/outcome catalog reader is still needed to find originals after
protected storage is cleared or a changed audience no longer renders the customer.
The backend unique approval/customer constraint refuses duplicate new preparation,
but the UI does not yet recover that original through its catalog. Protected deployed
invocation, authenticated provider evidence/operator resolution and retained
conversion remain pending. No delivery, physical or production acceptance claimed.

## Native retained intent and result reader (13AT)

A manager can explicitly read a campaign's retained intentions without loading
current recipients. Bounded pages default to 20, preserve failed offsets for retry,
and hide the entire previous page while reading or after invalid data. Each intent
must match its independently read ID/key, retained approval and historical contact
ID/key; the selected campaign must still match the current campaign original.
No current contact grant or account catalog is required for historical reading.
The rendered summary omits recipient destinations and device tokens. Actor/token
changes unmount readers; late replies cannot publish into a replacement session.

Each intent offers a separate explicit bounded outcome audit and current-head read.
Full outcome bindings/fingerprints/clocks and present predecessor relationships are
validated; every page original and current head is independently read by ID/key.
A present successor of the current head or contradictory present predecessor
refuses the read. The current head is reread before publishing; a changed head
hides results and asks for retry. Equal-clock observations are not assumed to have
chain order equal to their ID sort order. Predecessors outside the page remain
explicitly unverified. The reader reports unknown, rejected or accepted, a known
provider reference and no-result state. Accepted never means delivered. Reading
never prepares a new intent, submits/reconciles a provider or writes an outcome.

This supplies historical discovery after storage clearing/audience changes. New
preparation is still independently guarded by the backend's unique approval/customer
constraint; selecting an existing intent inside the preparation form remains future
UX work. Deployed protected invocation, authenticated evidence/operator resolution
and conversion attribution remain incomplete.

## Exact existing recipient intention (13AU)

Manager-only GET `campaigns/{campaign}/dispatch-intents/recipient/{customer}` with
required `expected_revision_id` selects the unique owned approval/customer intention
or explicit null. Institute lock, existing owned campaign, owned APPROVE revision
belonging to that campaign and owned customer are required. Receipt verification
rechecks full historical submission/fingerprint/sources; neither current recipient
permission nor current account configuration is consulted. An old retained approval
can be queried even after later campaign revisions. Null is absence, never permission
or evidence of no provider activity beyond this exact retained intention selection.

The preparation form offers explicit existing-intention discovery, including after
withdrawal, and consults the same exact selection before loading account choices.
Each discovery independently checks intent ID/key, historical approval/contact ID/key
and current selected campaign. An existing intention freezes new preparation, uses
no new key/session request and performs no POST. The historical actor may differ
from the current signed manager; recovery of a protected request still requires
its original actor/full terms. Existing protected or invalid storage blocks discovery
to preserve uncertain operations. Absence does not enable a withdrawn recipient.
Failed discovery hides account choices and allows clean retry; token replacement
prevents late publication. No mount read, account/provider configuration, submission,
reconciliation or outcome mutation is added. A concurrent creation after an absent
read is still resolved by the backend unique approval/customer constraint.

## Opt-in deployment invocation (13AV)

`python -m app.modules.marketing.invoke --institute INSTITUTE --intent INTENT
--expected-fingerprint SHA256` inspects one retained intention and current outcome.
All three selection arguments are required. Inspection performs no credential
resolution/provider I/O and creates no outcome. It does not prove readiness,
delivery or current permission. The command is not imported or scheduled by startup
and no public execution endpoint is added.

Execution additionally requires `--execute --receipt NEW_LOCAL_JSON_PATH`, automatic
schema creation disabled, PostgreSQL with exactly the checked-in Alembic heads and
a retained explicitly live account. The command never creates/migrates tables or
installs configuration, tokens, schedulers or credentials. A deployment operator must
configure the already documented accounts/bindings and apply/verify migrations
separately. The CLI always uses the trusted built-in transport registry, a fixed
worker actor and a single intent; it accepts no adapter plugin, credential or actor
argument. Internal tests inject a fake resolver only.

The expected fingerprint must equal the independently retained complete submission.
The existing worker still owns fresh first SEND/contact/permission/account checks,
commits uncertainty before provider I/O and reconciles only on every uncertain
reentry. Terminal reentry has no provider call. No automatic resend, bulk scan,
retry loop or daemon is introduced. Invocation is a local trusted server operation,
not a manager browser action.

The receipt path is reserved exclusively before execution; existing files/symlinks
are refused. The JSON is flushed and fsynced before stdout publication. It contains
only institute/intent/fingerprint/mode/operation/status/outcome ID and a strictly
false delivery flag, no contact destinations, provider credentials or raw errors.
Exit0 is a completed report (including unobserved inspection or provider rejection),
exit2 is a report with retained unknown status, exit1 is command failure. Provider
acceptance remains distinct from delivery. A failed invocation may leave an empty
or incomplete file and a committed uncertain/terminal DB observation: inspect
retained originals, never delete history or infer no attempt from a missing receipt.
A new receipt path permits recovery; durable worker state forbids automatic resend.

Tests use isolated owned PostgreSQL schemas with actual retained services and
explicitly live-mode fixture metadata plus fake adapters, never external providers.
The gate's Alembic stamp is a fixture on metadata-created test tables, not evidence
of a deployed migration. Actual production schema/backup/secret ownership/provider
acceptance remain unverified. Provider evidence/operator uncertainty resolution and
retained conversion attribution still require implementation and acceptance.

## Explicit billing attribution contracts (13AW)

`conversions.py` adds a pure source-backed manager-link contract and exact summary,
not an attribution API or persisted conversion ledger. A typed link includes the
complete retained intent and matching SHA-256 submission, exact unchanged SEND
successor of its approval, accepted outcome bound to the same account/key/fingerprint,
a scoped recorded closed-ticket fact, an explicit observed post-acceptance billing
window and manager actor/reason/operation key. Provider acceptance does not establish
delivery; an explicit manager link does not establish causal effect. Those flags
remain strictly false, including refusal of numeric/string boolean substitutes.

The billing ticket must belong to the exact institute/customer and fall inside
[start,end); the window starts no earlier than the observed acceptance and ends
no later than one shared billing capture. Outcome retention must be no later than
that capture. Both preparation-before-SEND and preparation-after-SEND are permitted
when authorization/preparation precede the provider observation and SEND follows
the retained approval. Historical link validation does not depend on current grant
or account configuration; it confers no execution authority. Shapes/fingerprints
do not authenticate callers, verify database originals or prove paid/provider facts.
The future retention service must independently fetch authoritative sources.

Summaries accept only links in an explicit owned campaign/time window, reject
duplicate ticket IDs and operation keys across included approvals, retain missing/
invalid amount diagnostics and separate test/live and CHF/EUR groups. Gross sums
are canonical integer minor-unit strings; unknown currency is counted separately
and never mixed or converted. These are linked recorded billing totals, not net
profit, causal incremental revenue or forecast. No conversion rate is invented
without a valid denominator and no ROAS without authoritative campaign spend; both
remain null. Summary completeness is strictly false: bounded/submitted cohorts
cannot represent complete campaign history.

Checked-in backend fixture projects exact intent/accepted outcome terms from the
13AR three-channel retained-service vectors, so backend collection is independent
of the frontend mount. SEND and closed-ticket/window facts are synthetic, and a
separate synthetic live-mode rehash verifies test/live separation. No actual sales
are attributed, no source records are updated and no provider I/O occurs. Durable
owned attribution originals/replay/correction/audit, independent paid-ticket source
capture, signed API/native tracking and authenticated provider evidence/operator
resolution remain required; Phase13 and production/physical gates remain OPEN.

## Authoritative attribution preview (13AX)

Manager-only POST `conversions/validate` accepts only selected intent ID/full
fingerprint, SEND original ID, accepted outcome ID, recorded billing ticket ID,
explicit start/end, reason and operation key. Actor is taken from the signed
manager session; supplied actors/full ticket/result/submission objects are refused.
The server locks the owned institute, takes one aware capture clock and independently
loads retained intent/authorization/outcome originals and the exact owned recipient's
recorded paid ticket. No client-supplied amount, destination or provider success is
used. A missing/wrong-recipient ticket, nonpaid/undated/future paid fact or wrong
source fingerprint/authorization/outcome/window refuses the preview.

Exact recorded ticket amounts reuse CRM's canonical minor-unit conversion and
missing/invalid diagnostics; currency is CHF/EUR or explicitly unknown. This source
is the application billing ledger's paid status and paid_at, not independent bank
or provider settlement proof. The complete Attribution contract is reevaluated
against the fetched originals and shared captured_at; no current permission or
account catalog can rewrite those historical originals.

Response contains the full selected source terms and an explicit `retained: false`.
The operation key is a proposed future link key, not a persisted replay receipt.
Reusing it for another preview does not freeze or create an original. No ticket,
intent, campaign or outcome is updated, no attribution retained, no provider called.
Participating billing corrections use the same institute lock: a correction waits
for preview capture, and a later preview observes the changed ticket. An old preview
must never be presented as current or used as a write authority without fresh capture.
Full declared contact facts in the retained intent remain signed-manager-only.
Durable link originals/corrections/audit, signed write/readonly catalog and native
tracking remain next; no conversion completion or production acceptance implied.

## Durable conversion schema foundation (13AY)

Alembic `4ab1d209558c` follows `3fa0c198447b` and adds conversion originals and
one current head per institute/recorded ticket. Each original holds event action
(linked/retracted), full proposed request and attribution JSON/fingerprint, actor,
reason, key/time and predecessor; source columns reference the owned billing ticket,
intent, campaign authorization and exact intent/outcome pair. Institute operation
keys are unique. Predecessor/head composite foreign keys pin the same institute and
ticket; self predecessors, unknown actions and predecessor-free retractions refuse.
A single head per ticket provides the structure for preventing double attribution
across campaigns; the forthcoming write service must serialize/validate transitions.

Database relationships are structural, not source authenticity or conversion
semantics. They do not prove SEND stage, accepted status, ticket customer ownership,
exact capture/fingerprint, valid snapshots or correct chain transitions. Existing
authoritative preview and pure contracts must be applied by the future receipt/write
service. No append/retract API, data backfill, attribution service write or native
conversion tracking is introduced by this schema checkpoint. Direct administrative
SQL is not constrained to be append-only; application services must preserve history.

An online downgrade refuses if either conversion originals or heads exist; offline
downgrade refuses without examining history. An empty owned schema can downgrade
to its parent and upgrade again. This migration is additive and does not modify
recorded tickets or previous source ledgers. It was applied only to owned disposable
SQLite/PostgreSQL test databases. No existing application database was migrated.
The opt-in invocation CLI derives expected heads from the checked-in migration graph
and now requires this head in a deployment, rather than silently accepting the
previous schema. Production migration/locks/backup acceptance remain OPEN.

## Retained attribution events (13AZ)

Manager-only POST `conversions` retains linked/retracted events. A link supplies
ticket, exact current predecessor (null only with no history), selected authoritative
preview terms, reason/key. Selection ticket/reason/key must match event terms; the
server freshly captures sources, never accepts a returned preview as write authority.
Retraction supplies no new selection and preserves the exact linked predecessor's
full attribution snapshot. A subsequent link can freshly capture corrected billing
or explicit campaign reassignment using the current predecessor and a new key.
Each event carries its own actor/reason/key/time; the retraction snapshot retains
the original attribution actor/key/capture, rather than rewriting historical facts.

Original-key replay checks full request and signed actor before any current pointer,
clock or billing capture. Old original recovery remains possible after correction,
retraction or missing current pointer. New keys require the exact current head;
history with a missing pointer refuses a new initial link. Institute locking and
atomic original/head flush+commit prevent competing initial keys both winning;
head persistence failure rolls back the original too. No provider/outcome writes.

GET `conversions/original/{key}`, `conversions/{id}`, ticket current and audit reads
are manager-only. Receipt validates event columns, complete UTC-canonical SHA-256
attribution, full immutable intent/SEND/outcome originals and entire predecessor
chain. It preserves recorded billing snapshot even after ticket correction; it does
not recapture price for historical reads. Retraction requires a linked predecessor
and identical full snapshot; ticket/clock/cycles are checked. Verification refuses
chains beyond 1000 events rather than publishing partially verified history. Audit
pages default20/max50 with exact total/slice/created-at-ID ordering; equal-clock IDs
do not define predecessor order. These page bounds do not bound all source-proof SQL
reads; large-history performance remains unverified.

There is one current head per owned ticket across campaigns. Retracted events remain
in audit and never imply deleting history or undoing the sale. Campaign reports
select only current linked events, separating test/live and currency
and preserving unknown amounts; no campaign conversion dashboard/native writer yet.
No statistical causal lift, delivery or bank settlement is proven. Actual provider
evidence/operator resolution and production/physical acceptance remain OPEN.

### Phase13BA current conversion cohort and summary

Manager-only GET `campaigns/{id}/conversions/current` and `/summary` require
explicit aware `start`/`end`, a positive half-open recorded billing window fully
observed at one server capture. The institute lock protects the entire read.
Every historical ticket candidate for the owned campaign is checked through its
current original and complete predecessor/source proof before publication, even
outside the requested page or window. Missing heads, future events and incoherent
receipts refuse publication. Retracted or reassigned current events are excluded.
Current pages default20/max50, ordered by ticket ID, with an exact total; the
requested page is bounded but the verification work scans the entire candidate
cohort. Large-history performance remains unverified.

The summary consumes all current selected links, not just a page. It reports exact
minor-unit amounts per known currency and live/test mode, retaining missing/invalid
amount and unknown-currency diagnostics. A billing correction alone does not
rewrite an attribution snapshot; a new explicit linked event replaces the current
amount without double counting its predecessor. `full_retained_current_cohort`
means all retained current declared links in this window, not all sales, all
conversions or complete campaign history. Conversion rate and ROAS remain null;
causal lift and delivery are unproven. Candidate discovery trusts stored campaign
scope metadata; hashes detect incoherent retained receipts, not authenticated
provider evidence or arbitrary administrator rewriting of the database.
