# Phase 13 Marketing acceptance evidence

Canonical authority: Master Plan section 34. Gates remain OPEN:
SEGMENTATION, CAMPAIGN_DRAFT, CAMPAIGN_APPROVAL, CAMPAIGN_AUDIT.

## 13A: explicit campaign approval foundation

`backend/app/modules/marketing/campaigns.py` provides pure immutable audience,
content and revision facts plus DRAFT -> REVIEW -> APPROVE -> SEND transitions.
Human and AI origin follow identical review/approval. SMS/email/push are explicit;
email requires subject, other channels have none. Audience is nonempty/unique,
scope matches content, snapshot/revision clocks are aware and monotonic. Review
and approval pin a canonical SHA256 of literal content/template/audience/recipient
order and normalized snapshot clock. Editing content or audience resets approval
and review to DRAFT. Stage changes cannot inject new content, stale predecessors
cannot transition and SEND cannot be edited in place. Nested facts are revalidated.

SEND is currently a pure dispatch-request stage, not a delivery receipt. Every
revision explicitly retains external_message_sent=false/delivery_authorized=false.
Pure caller-supplied audience/actor facts do not establish registered customer,
signed role/ownership, destination, consent, provider authority or persisted audit.
Those checks must be implemented in the source-backed services before dispatch.
No external messages, API write or production provider configuration performed.

Evidence: 9 new marketing cases plus adjacent lifecycle/automation/reconciliation
regression: 46 passed in 0.58s, zero failures/skips, native Windows Python. Covers
all channels/origins, chain order, edits resetting digests, injected/mutated content,
foreign ownership, future audience, stale/self predecessor, backward clock,
duplicate/whitespace members. Existing Starlette/httpx deprecation only. No
PostgreSQL/migration/frontend/browser/provider acceptance inferred.

## 13B: owned segmentation and marketing permission observations

Readonly signed manager POST audience-observations requires explicit segment set,
channel and nullable exact cursor. Keyset scan returns <=50 own registered customer
IDs plus next cursor; page is not an immutable complete institute audience. One
institute lock/clock pins each member profile, selected state and scoped lifecycle
declaration. Internal profile capture-clock injection preserves existing defaults
and six-query profile budget. Permission is purpose/channel-specific: follow-up
never implies marketing; missing/refused/future declarations cannot qualify, push
is unsupported until a declared source exists. Granted recorded permission and
selected segment do not prove reachable contact/provider authority; delivery
remains false. No raw destination contact list or external communication produced.

Initial adjacent focus: 15 passed in 13.87s. Final new audience/campaign/profile/
lifecycle regression: 20 passed in 23.37s, zero failures/skips, actual PostgreSQL
enabled. SQLite/PostgreSQL cases scan 55 owned members in 50/5 pages, exclude
foreign same-name member, verify shared clock/missing policy, marketing grant/
refusal/unknown versus follow-up-only and future declaration, SMS/push separation,
signed roles/owner/unauthenticated and invalid selections. Existing passlib crypt
warning only. No migration/native/browser/production acceptance inferred. All
four Phase 13 gates remain OPEN pending retained audience/campaign workflows.

## 13C: replayable audience coherence

Audience page validation now independently recomputes selected segment from retained
policy/customer/billing/diagnostics and eligibility from exact channel/marketing
permission original. Strict booleans, owned nested dimensions, shared microsecond
clock, <=50 ordered unique members, cursor bounds and full-page next cursor pin
are enforced. JSON roundtrip succeeds; forged VIP, eligibility/permission/selection,
foreign nested customer, reversed members, forged cursor and microsecond capture
change fail on both SQLite/PostgreSQL source fixtures. Adjacent audience/campaign/
profile regression: 15 passed in 14.61s, zero failures/skips, actual PostgreSQL.
Existing passlib crypt warning only. This establishes coherent replay contracts,
not database completeness, persisted original authority or permission to send.
Immutable audience schema/service is still pending; all marketing gates OPEN.

## 13D: audience original/page schema

Added audience original table (owned actor/reason/key/capture clock/request/summary)
and retained page table (owned capture, nonnegative page index and observation
JSON). Composite owner/capture foreign key rejects cross-institute page links;
original key is unique per institute, page index unique per owned capture. Migration
`0c7d9ef65148` follows `fb6c8de54037`, matches ORM metadata and refuses offline
history verification or removal of any retained audience row. No production
migration was applied. Typed capture persistence/replay service remains pending;
schema fixture JSON is not a validated audience or delivery authority.

SQLite/actual PostgreSQL schema focus: 2 passed in 10.07s, including empty roundtrip,
metadata comparison, foreign page/negative index/duplicate key refusal and protected
history. Adjacent audience/campaign tests: 11 passed in 9.40s. Full migration
regression (all 22 files, actual PostgreSQL enabled): 45 passed in 270.48s,
zero failures/skips, terminal exit 0. Existing passlib crypt and SQLite datetime
adapter deprecations only. Prior migration tests change only expected latest head;
original downgrade targets and retention assertions remain unchanged. All Phase
13 gates remain OPEN.

## 13E: atomic retained audience capture

Signed manager POST audience-captures takes explicit segments/channel/reason/key,
scans all registered own customers through 50-member pages under one institute
lock/server clock, retains each validated observation and commits original/final
summary/pages once. Exact counts/page arithmetic checked. Original-key replay
precedes new source/clock, pins actor/full literal terms; changed actor/terms fail.
Scoped original-key/ID reads return bounded metadata; retained-page reads validate
scope/clock/filter and cursor/end chain, including predecessor's filter. No edits
or deletion routes. Historical eligibility never grants fresh contact/provider/send
authority; delivery_authorized remains false. Complete registered cohort is the
capture-time owned record cohort, not guaranteed complete historical customer data.

Initial adjacent regression: 13 passed in 16.49s; expanded audience/campaign/profile:
18 passed in 26.56s; final tightened page predecessor-filter focus: 3 passed in
12.69s, actual PostgreSQL enabled, zero failures/skips. Real 55-member capture,
50/5 historical pages, one clock, summary, backward-clock original replay, changed
actor/terms/foreign/out-of-range, signed key/ID/page and role denial, injected second
page flush rollback preserving old history, forged predecessor filter and competing
same-key one original/two pages tested. Existing passlib crypt warning only. No
schema/native/browser/provider/production receipt inferred; marketing gates OPEN.

## 13F: verified campaign audience binding

Internal campaign_audience reads an owned retained capture for the exact requested
channel, checks actual stored page count, validates every historical page/chain and
reconciles whole customer/selected/eligible counts against summary. Only recorded
marketing-eligible recipient IDs are returned in deterministic retained order with
capture ID/clock for approval digest. Wrong channel, foreign ID, manifest mismatch
and empty eligible list fail. This is historical campaign content binding, not
fresh permission/contact/provider authority or a campaign persistence endpoint.

Initial source/campaign focus: 12 passed in 14.01s; expanded adjacent regression:
14 passed in 20.01s; final tightened source focus: 3 passed in 13.66s, actual
PostgreSQL, zero failures/skips. Eligible recipients on both pages of a 55-member
50/5 cohort prove no first-page truncation. Forged summary and foreign/channel
changes refused, rollback restores original, empty SMS permission cannot qualify.
Existing atomic/replay/concurrent-key and approval chain tests remain passing.
Passlib crypt deprecation only; no schema/native/provider/production claim. All
marketing gates remain OPEN pending campaign/template persistence and workflows.

## 13G: owned template/campaign revision schema

Added template originals/current heads and campaign originals/current heads.
Original rows retain signed-actor/reason/key/clock/request slots and typed-content
or revision JSON slots for the forthcoming service. Template predecessor/head
must belong to the same institute/template; campaign predecessor/head must belong
to the same institute/campaign. Campaign audience and optional template original
are scoped composite foreign keys. Replay keys are unique per institute/domain.
Migration `1d8eaf762259` follows `0c7d9ef65148`, matches metadata and refuses
removal of any retained campaign/template history (or offline history checks).
No production migration or campaign/template write/approval API implemented here.
Schema fixtures are explicitly not validated campaign/audience business receipts.

SQLite/actual PostgreSQL new migration focus: 2 passed in 10.22s; exact metadata,
empty roundtrip, cross-root predecessor/head, foreign source and duplicate key
refusal, retained-history protection. Adjacent audience/campaign services:
14 passed in 25.56s, zero failures/skips. Full migration suite (all 23 files, actual PostgreSQL): 47 passed in 286.73s,
zero failures/skips, terminal exit 0. Existing passlib crypt/SQLite datetime adapter
deprecations only. Prior
fourteen latest-head assertions update only revision value; prior downgrade and
history assertions remain intact. All Phase 13 gates remain OPEN.

## 13H: signed template originals and corrections

Signed manager templates POST and original-key/original-ID/current reads now use
explicit new-root/correction targets and literal plain-text name/channel/origin/
subject/body. Email requires subject; SMS/push have none. Placeholder text is
preserved literally, not rendered. Full original request/actor/content retained;
key-first replay precedes mutable clock/head and pins terms/actor. Correction pins
exact current predecessor/monotonic clock; original/head commit once or rollback.
No edit/delete/render/send API or provider authority.

Initial adjacent focus: 11 passed in 4.61s. Expanded template/audience/campaign:
15 passed in 19.45s, actual PostgreSQL, zero failures/skips. Final six pure channel/
origin cases on Windows: 6 passed in 0.21s (three DB cases deselected). SQLite/
PostgreSQL current/history/replay, signed key/ID/current/role checks, actor/terms/
stale/clock refusals, original-flush then head-failure rollback and concurrent
correction one winner covered. Existing passlib crypt and Windows Starlette/httpx
deprecations only. No schema/native/provider/production acceptance inferred;
campaign draft/review/approve/audit persistence remains pending; gates OPEN.

## 13I: source-bound campaign originals, approval and audit

Signed manager campaign create/edit/review/approve now persist immutable request/
revision/actor/clock and update owned current head atomically. Explicit source IDs
are resolved server-side; caller recipient/actor lists are not accepted. Audience
is verified across all retained pages; optional template must match literal content
and not be from the future. Review/approval reverify these retained sources. Exact
predecessor and pure review chain enforced; edits clear review/approval digests.
Key-first replay pins actor/full terms before mutable head/clock. Independent
original-key/ID/current and bounded 20/default 50/max audit/total reads retain all
versions. Audit timestamp/ID ordering exposes predecessor IDs for causal history.
SEND is not yet an API action; fresh destination/permission/provider integration
is pending and delivery/sent flags remain false. No message/provider operation.

Initial focus: 11 passed in 16.29s. Five-file marketing regression: 26 passed in
41.92s, zero failures/skips, actual PostgreSQL. Final audit focus: 3 passed in
16.40s. Source-bound two recipients across 50/5 cohort, template exactness, review/
approve/edit reset, signed roles/key/ID/current, actor/terms/scope/stale/backward
clock refusals, injected original/head rollback, immutable history, competing
same-key creation and review one winner, audit 2/2 pages/total/max bound and SEND
422 tested. Existing passlib crypt warning only. No schema/native/provider/
production acceptance inferred; all Phase 13 gates remain OPEN.

## 13J: bounded owned marketing catalogs

Signed manager GET catalogs expose retained audience captures and current template/
campaign originals with exact total/offset/limit and 20-default/50-maximum pages.
Head joins pin institute, root and original ID; missing/incoherent originals refuse
rather than returning an incomplete page. Corrections retain one selectable root.
Typed page validation requires returned item count to agree with total and bounds.
No schema change, provider call or external delivery authority.

Full six-file marketing regression, SQLite/actual PostgreSQL: 28 passed in 53.58s,
zero failures/skips. Covers 24 template roots in 20/4 pages, correction selection,
empty end page, three-query template budget, campaign/audience pages, foreign scope,
signed manager-only routes, invalid bounds, page coherence and OpenAPI generation.
Existing passlib crypt deprecation only. Native workflows, delivery and conversion
remain pending; all Phase 13 gates remain OPEN.

## 13K: native template receipt contracts

Typed template content/request/original/catalog guards now verify owned scope,
root/predecessor coherence, literal content equality and actor-bound receipt terms.
Independent originals compare exact microsecond instants, accepting equivalent
UTC offset spelling. Content retains whitespace/placeholders; Python-compatible
Unicode code-point bounds support non-BMP characters. Catalog guards pin requested
offset/limit, exact total-derived item count and unique ordered roots. Unknown fields,
foreign originals, duplicate/reordered roots and altered terms fail closed.

Three final focused contract tests pass. Full frontend regression: 285 passed in
77.45s, zero failures/skips, terminal exit 0. TypeScript/Vite build passes with 129
modules after using a compatible own-property check. No editor/browser/backend/
provider acceptance inferred. Phase 13 gates remain OPEN.

## 13L: native audience receipt and retained-page contracts

Native guards validate explicit selection, actor-bound original terms and exact
manifest/page arithmetic. Observation guards reuse CRM classification and lifecycle
source guards, recompute marketing-only permissions and eligibility, enforce owned
unique ordered customers/shared clock and refuse delivery authority. Retained pages
pin original/filter/index/clock/predecessor cursor/exact size/end. Catalogs require
requested bounds, total-derived count and descending clock/ascending ID tie order.

Initial three tests pass; final four focused tests pass with catalog coverage.
Full frontend regression before catalog addition: 288 passed in 53.11s, zero
failures/skips, terminal exit 0. A real SQLite backend original-service fixture
export (55 customers, retained 50/5 pages) passes the native guards with exact
selected summary, two eligible recipients and terminal null cursor. Temporary
owned DB cleaned; existing Starlette/httpx and bcrypt-version warnings only.
Final TypeScript/Vite build passes (129 modules), terminal exit 0.
No signed native UI/browser/provider/production acceptance inferred; gates OPEN.

## 13M: native campaign digests and receipts

Native campaign content/action/original/catalog guards now enforce source scope,
unique explicit recipient IDs, monotonic audience capture, exact request/receipt
root/predecessor/reason/content and DRAFT/REVIEW/APPROVE state. Review/approval use
WebCrypto SHA-256 over Python-compatible sorted compact ASCII JSON with normalized
UTC microseconds; recipient order, Unicode/literal text and template ID remain
pinned. Delivery/sent authority and SEND action refused. Actor/full-term matching
and independent original comparison support forthcoming protected recovery.

Three focused tests pass. Full frontend: 292 passed in 48.47s, zero failures/skips,
terminal exit 0. TypeScript/Vite build passes (129 modules). Three independently
computed Python Unicode/DEL/UTC/microsecond vectors, including before epoch, agree.
Initial PowerShell Unicode vector corruption was corrected with explicit Python
escapes. Five actual SQLite original-service receipts (draft/review/approve/edit
reset/template-bound) pass native validation/comparison; reviewed digests agree.
Fixture owned DB cleaned; existing Starlette/httpx/bcrypt-version warnings only.
Audit guards/editor/browser/delivery/conversion remain pending; all gates OPEN.

## 13N: native campaign catalog and bounded history

Manager-only lazy Marketing navigation now exposes paginated current campaigns,
literal retained content, source audience count and revision evidence. Selected
current receipt must agree with independent original-ID read before display.
Audit guards pin scope/bounds/total-derived count, original digests and ascending
clock/ID ordering. Present explicit predecessors verify stage/content continuity;
equal-clock ID ordering is display order, not causal order. Bounded pages can omit
predecessors and do not claim complete-chain verification. Fresh reads clear old
facts; failure hides history/content; late old session/institute/selection responses
cannot publish. No editor or review/approval/send controls implemented here.

Six focused tests pass. Full frontend: 295 passed in 50.77s, zero failures/skips,
terminal exit 0. Final two native tests pass after wrapping/control style refinement;
TypeScript/Vite build passes (132 modules). Signed headers, independent reads,
corrupt total hides facts then clean retry restores, literal script escaping, role
and late-scope isolation plus audit ordering/duplicates/predecessors tested.
Browser geometry and signed Edge acceptance remain pending; all gates OPEN.

## 13O: native review/approval and protected recovery

Selected verified campaign now exposes review from DRAFT and approval from REVIEW,
with explicit reason and exact current revision. Requests retain null content and
cannot change audience/text during validation. Full request is stored per institute/
signed actor/campaign before key lookup or POST. Resume uses the retained key;
receipt actor/terms/digests, independent key/ID originals and owned current head
must verify before exact stored intent clears. Advanced current head is allowed;
immutable receipt remains pinned. Invalid storage or corrupt/wrong-actor reads keep
the intent and block new writes. Only a definitive POST business refusal exposes
explicit correction reset. No SEND/provider action. Session checked after async
receipt digest before further reads; selected-history head has the same guard.

Five focused action/history tests pass; final three action tests pass after replacing
a fixed 40ms test wait with a bounded wait for the action to settle. Initial full
frontend run had 297 passes/one failure from the premature recovery assertion;
final full frontend: 298 passed in 82.05s, zero failures/skips, terminal exit 0.
Final TypeScript/Vite build passes (133 modules).
Lost committed reply survives remount with one POST; independent key/ID/current,
wrong actor/forged head preserve intent, invalid SEND storage/reception deny writes.
Native draft/edit and audience/template editors plus signed Edge acceptance remain
pending; all gates OPEN. No production or external delivery acceptance inferred.

## 13P: native audience capture and signed recovery

Marketing now includes explicit six-segment/channel/reason capture form without
implicit selections. Full request/key is stored per institute/signed actor before
original lookup/POST. Exact returned actor/terms/manifest plus independent key/ID
originals must agree before stored intent clears. Invalid/changed/corrupt reads
retain intent and freeze writes; only definitive POST business refusal permits
explicit correction. Retained capture is immutable, no delivery authority inferred.
Push unsupported permission is explicit. Counts distinguish observed/selected/
recorded-permission eligible clients; no current-send permission claim.

Four focused audience/history tests pass, including actor/independent summary
mismatch, invalid storage, exact closure, late actor response and role denial.
Full frontend: 300 passed in 58.73s, zero failures/skips, terminal exit 0.
Initial actual signed Edge desktop/touch-tablet: two passed in 52.2s. After visual
inspection improved the narrow fieldset into a responsive grid, final two passed
in 44.5s; fixture cleaned and both final screenshots inspected. Signed source CRM
policy/permission creation, explicit selection, committed/lost reply/reload/key
recovery with one POST, unchanged original-ID receipt, retained eligible client,
>=44px controls/no overflow verified. TypeScript/Vite build passes (135 modules);
launcher rebuilt final styling. Existing bcrypt-version/NO_COLOR warnings only.
Catalog/page selection, templates/campaign editors and full campaign desktop/tablet
acceptance remain pending; all marketing gates OPEN. Physical/production gates OPEN.

## 13Q: native retained-audience catalog and pages

Marketing now exposes owned bounded 20-member capture catalogs and historical
client pages. Each selected page rereads original ID/key independently and compares
immutable receipt before retained source/filter/clock/index/count/eligibility guard.
Next cursors come from verified page; prior pages use already verified cursor map.
Fresh loads clear client articles; failed validation hides them, clean retry restores.
Successful capture resets stale catalog selection; late old session/selection reads
cannot publish. Historical permission is labeled and does not authorize delivery.

Six focused native catalog/capture/history tests: passed in 4.87s. Full frontend:
302 passed in 57.46s, zero failures/skips, terminal exit 0. TypeScript/Vite build
passes (136 modules). Actual signed Edge desktop/touch-tablet expanded scenarios:
2 passed in 43.8s, fixture cleaned. Real registered 55/56 cohorts yield retained
50/5 and 50/6 pages, independent original read, lost reply/key recovery one POST,
catalog selection, backward/forward cursors. Forged selected-segment page hides
all old articles, clean reread restores exact remainder. Final screenshots inspected;
existing bcrypt-version/NO_COLOR warnings only. Template/campaign editors and
complete signed approval/audit acceptance pending; all marketing gates OPEN.

## 13R: native template editor, correction and recovery

Manager native templates now provide explicit new/correction targets, bounded
current-root catalog and owned current/independent-ID preparation. Channel/origin
must be chosen; email-only subject and literal body preserve whitespace, Unicode
and placeholders. Correction pins exact current predecessor, original is immutable.
AI origin is declared provenance, not generation. Full request/key stored per
institute/actor before lookup/POST; exact actor/terms/receipt plus independent key/
ID/current root checks precede clearing intent. Failed/foreign reads retain intent;
invalid storage freezes writes; only definitive POST business refusal permits
explicit correction reset. Async preparation uses token/mount/sequence guards.

Four focused native tests pass; final two template tests pass after scope/wrapping
refinement. Full frontend run: 304 passed in 76.20s, zero failures/skips, terminal
exit 0. Final TypeScript/Vite build passes (137 modules). Actual signed Edge
scenarios initially exposed test synchronization issues: matching textarea before
receipt and checking resume before intercepted reply finished. Both fixed by
waiting on actual lost reply and verified receipt. Corrected desktop/tablet runs:
2 passed in 37.7s; final expanded editor geometry/screenshots: 2 passed in 37.4s,
fixture cleaned. One creation POST recovered after reload; literal Unicode/subject/
body/placeholder/script escaped; email-AI to SMS-human correction exact predecessor;
old ID unchanged, current exact, one selected root and protected storage cleared.
Form/result controls >=44px, no overflow, screenshots inspected on both formats.
Existing bcrypt-version/NO_COLOR warnings only; no provider or production claim.
Campaign draft/edit source selection and complete approval/audit acceptance pending;
all marketing gates OPEN, physical/production gates OPEN.

## 13S: native source-bound campaign creation and signed approval chain

Native campaign creator explicitly chooses channel/audience/text mode/content/reason.
Bounded owned source catalogs disable wrong-channel/empty eligible choices. Selected
audience ID/key and template original ID must independently agree with catalog
originals. Template mode copies/locks exact literal content/provenance and pins ID;
literal mode is explicit. Backend resolves recipients across retained audience pages;
no native raw-recipient input or historical-permission-as-send-authority assumption.
Full generated-key create intent stored per institute/actor; actor/terms/DRAFT receipt,
independent key/ID/current-root and exact stored request verify before closure.
Corrupt reads preserve intent; successful create refreshes catalog; no SEND action.

Five focused creator/history tests pass in 3.87s. Full frontend: 307 passed in
58.99s, zero failures/skips, terminal exit 0. TypeScript/Vite build passes (138
modules). Actual signed Edge desktop/touch-tablet: 2 passed in 42.4s; fixture cleaned.
Signed source policy/permission/capture/template, exact UI source selection, literal
Unicode body, committed/lost draft reply/reload with one POST, REVIEW -> APPROVE,
three retained audit originals, old draft unchanged, approval digests equal and
sent/delivery false, protected keys cleared. Creator controls >=44px/no overflow;
four draft/approved screenshots inspected. Existing bcrypt-version/NO_COLOR only.
Native edit/reset and deeper page/all-channel acceptance plus contacts/delivery/
conversion pending; all marketing gates OPEN, physical/production gates OPEN.

## 13T: native campaign editing and approval reset

Selected campaigns now reuse the source-bound editor for exact-predecessor edits.
Preparation independently rereads current/ID and retained audience ID/key/channel/
clock/eligible count, optional exact owned nonfuture template original/content.
Source mismatch refuses the form. Literal/template fields prefill without guessing;
explicit literal-mode switch releases template binding. Per-institute/actor/root
edit intent survives refresh/reload; original-key full terms/actor plus independent
key/ID/current checks precede closure. Backend edit creates DRAFT, clears review/
approval digests and preserves all older originals. No SEND/provider operation.

Five creator tests pass in 2.90s, including wrong edit actor/receipt closure with no
POST, forged source clock refuses preparation then exact prefill and prior guards.
Full frontend: 309 passed in 58.06s, zero failures/skips, terminal exit 0. TypeScript/
Vite build passes (138 modules). Actual signed desktop/touch-tablet full expanded
workflow: 2 passed in 48.8s; fixture cleaned. Approved AI/template-bound campaign
explicitly released to human literal correction, exact approval predecessor, lost
edit/reload/replay four total POSTs, DRAFT/null digests/new review required, original
approval unchanged, four audit originals and edit storage cleared. Controls >=44px/
no overflow; four edit/reset screenshots inspected. Existing bcrypt/NO_COLOR only.
All-channel/source replacement/deeper pagination and contact/delivery/conversion
acceptance pending; marketing gates OPEN, physical/production gates OPEN.

## 13U: native campaign pagination and refusal retry

Requested catalog/audit offsets now survive a refused fresh read independently of
accepted page data. Stale facts/actions remain hidden; explicit refresh retries the
same requested page. The audit guard also rejects predecessor cycles among originals
present on its bounded page, without claiming complete-chain validation outside it.

Six focused campaign/history tests pass in 2.78s. Full frontend: 309 passed in
60.91s, zero failures/skips, terminal exit 0. Signed launcher rebuilt final TypeScript/
Vite source. Actual Edge desktop/touch-tablet scenarios: 2 passed in 53.5s; fixture
cleaned. Each selected campaign has 24 immutable revisions (20/4 pages); owned
catalogs contain 24 then 25 roots (20/4 then 20/5 pages). Forged final-page totals
hide stale facts/actions; clean retry preserves offset 20; backward/forward reads
restore exact counts. Initial expanded run exposed a real retry-offset defect,
corrected before the passing run. Both audit screenshots inspected. Marketing gates
remain OPEN; all-channel/source replacement, contacts/delivery/conversion acceptance
still pending. Physical/production gates OPEN; full canonical goal ACTIVE.

## 13V: signed native email-to-SMS source replacement

Actual signed native workflow now proves email/AI template draft, review, approval,
then exact-predecessor correction to independently verified SMS audience/template,
reset DRAFT and renewed review/approval. Channel change invalidates prior source
selection and removes email subject. Wrong-channel choices disabled. Internally
coherent forged template request/content disagrees with retained catalog original,
refuses selection and writes; clean reread restores exact locked SMS content. Later
template correction cannot replace the campaign's pinned original. Old email approval
unchanged; six native campaign POSTs/six audit revisions, distinct approved digests,
sent/delivery flags false.

Edge desktop/touch-tablet: 2 passed in 46.5s, terminal exit 0; owned fixture cleaned.
Final TypeScript/Vite source rebuilt. Editor controls >=44px/no horizontal overflow;
four source/approval screenshots inspected. Push capture zero eligible recipients:
current lifecycle declarations do not support push permissions. Native selection
refuses; direct attempted draft returns 400 with no retained replay original. This
is refusal acceptance only; canonical push integration remains incomplete. Existing
bcrypt-version/NO_COLOR warnings only. Test/docs-only change; latest full frontend
309 passed in 60.91s at 13U, no new full frontend/backend/provider claim.

Next: explicit immutable contact/permission support across all three channels,
provider/send/conversion integration and remaining source-catalog acceptance.
All marketing gates OPEN; physical/production gates OPEN; full canonical goal ACTIVE.

## 13W: explicit three-channel marketing contact declarations

Pure contact facts explicitly declare email/SMS/push permissions exactly once,
including unknowns, with independent destination/permission evidence. EmailStr
validates/normalizes email; SMS requires explicit international numeric format;
push binds application/token. Mixed/missing channel-specific fields refused.
Addresses/tokens excluded from repr, not from explicit serializable declarations.
No inferred customer phone endpoint, cross-channel permission or legacy lifecycle
migration. Existing four-dimensional CRM lifecycle facts remain unchanged.

Pure append validates supplied owned registered customer/current predecessor and
aware monotonic clocks; correction preserves predecessor. Pure evaluation checks
approved campaign, retained membership, own registration/declaration, observation
clock, declared grant and destination. Missing/unknown/refused/future sources refuse.
Nested model_copy values revalidated at entry. This does not establish that a caller
supplied the current database head, verified destination ownership/reachability or
provider authority; delivery/sent remain false. Persistence must supply owned current
originals under the transaction boundary before this can support actual sending.

Initial contacts/campaign: 14 passed in 0.32s. Final contacts/campaign/legacy lifecycle:
31 passed in 0.56s, terminal exit 0. Intermediate wrong test filename collected none;
corrected actual 12s file used for final verification. All channels, withdrawals,
owned/stale/predecessor/self/clock refusal, complete fields, destination mismatches,
forged nested sources/results and authority flags tested. Starlette/httpx deprecation
only. No schema/API/native/provider/full-suite acceptance claimed. Next: append-only
owned contact originals/heads and signed protected replay, coherent audience/fresh
send evaluation, provider transport and conversion. All gates OPEN; goal ACTIVE.

## 13X: contact original/head database schema

Migration 2e9fb087336a adds marketing contact originals and current pointers after
1d8eaf762259. Own institute/customer/predecessor identifiers, actor/reason/replay key,
aware creation clock and explicit declaration JSON retained. Composite predecessor/
head references pin the same institute/customer; per-institute key uniqueness and
self-predecessor check enforced. Customer FK requires an existing customer; initial
customer/institute ownership must additionally be checked by the signed service,
consistent with legacy CRM conventions. Tables do not themselves enforce raw-SQL
immutability; no mutation API introduced here. Alembic explicitly imports marketing
metadata rather than depending on unrelated test/runtime imports.

Empty downgrade/re-upgrade and exact metadata parity tested on SQLite/PostgreSQL;
invalid cross-customer/institute predecessor/head, duplicate key, missing customer
and self predecessor rejected. Correction preserves older declaration. Populated
history refuses downgrade without changing version/tables/rows, including originals
without any selected head. Offline downgrade explicitly refuses, verified separately.
Focused migration: 2 passed in 12.74s. Seven adjacent marketing test files: 34 passed
in 93.16s, terminal exit 0, actual PostgreSQL persistence cases. Existing crypt warning
only. Full 24 migration files: 49 passed in 327.70s, terminal exit 0, including
SQLite/actual PostgreSQL and prior history downgrade guards. Fourteen older expected
head assertions updated only to new revision. Existing SQLite datetime deprecation
also observed. No production migration/provider operation performed. Signed persistence/API/audience integration/native contacts
and delivery/conversion still required. All gates OPEN; full goal ACTIVE.

## 13Y: signed contact original service and protected replay

Manager-only contact POST and independent key/ID/current GETs require own registered
customer. Institute-scoped keys cannot expose another customer's declaration. Replay
requires original signed actor/full terms and occurs before head/clock reads, even
after a later correction. New correction pins current predecessor and monotonic
registration/predecessor clock. Original/head flush and validated receipt precede
one commit; write failure rolls back both. No update/delete route or provider call.
Retained reads reject incoherent JSON ownership and stored reason/key normalization
mismatch. Signed role/owner guards and strict injected actor rejection tested.
OpenAPI POST/three GETs and strict Request schema verified.

Initial service/pure: 11 passed in 10.97s. Full eight non-migration marketing files:
39 passed in 166.27s, terminal exit 0, actual PostgreSQL. Final stored-term coherence
refinement followed by all five service tests: 5 passed in 10.63s, terminal exit 0.
Same-key concurrent correction one identical receipt, competing predecessor one
winner, injected head failure rollback, historical replay before head/clock, altered
actor/terms/customer/stale/foreign/opaque and corrupt scope/terms refusal covered.
Existing crypt warning only; no new schema/native/provider/full-backend claim.

Three-channel declarations are not yet audience-capture evidence or fresh-send
reads. Next: coherent audience integration with legacy retained-page compatibility,
owned current declaration evaluation, native contact editing/recovery, provider
transport/send and conversion. All marketing/physical/production gates OPEN;
full canonical goal ACTIVE. No external message or production configuration.

## 13Z: current declared recipient observation pages

Signed manager GET requires exact current campaign revision and bounded offset/limit
(default20/max50). Own institute lock covers current campaign and contact declarations,
with one observation clock per page. Retained campaign member IDs/order/total stay
historical; current own registered customer/contact original reread for each member.
Historical lifecycle grant alone cannot establish a fresh destination declaration.
Withdrawal/absent/unknown/future/current DRAFT refuse eligibility; campaign head
change refuses the prior expected revision. No write/send/provider operation.

Typed page retains campaign original once, current source facts and strict derived
eligibility/reason. Guard checks campaign request/revision coherence, owned exact
revision/count/order/page bounds and recomputes each observation. Complete-campaign,
delivery/sent remain false; no cross-page atomicity, provider authority or delivered
result claimed. Missing/foreign/corrupted source refuses a whole read.

Initial SQLite/PostgreSQL: 2 passed in 12.43s. Final observation/contact/campaign
service regression: 11 passed in 49.79s, terminal exit 0. Two retained members through
1/1 pages, historical grant vs absent current declaration, withdrawal/future source,
stale campaign after edit, role/foreign/anonymous, bounds and forged page terms/count/
order/scope/eligibility/authority refusal covered. PostgreSQL writer attempts FOR
UPDATE and waits while sampled observation holds institute lock; page retains old
original, subsequent read sees committed withdrawal. OpenAPI required revision,
max50 and nonnegative offset verified. Crypt deprecation only. No new full backend,
schema/native/provider acceptance. Coherent three-channel audiences with legacy
retained-page compatibility, native contacts/observations, provider/send/conversion
still pending. All gates OPEN; full canonical goal ACTIVE.

## 13AA: explicit contact-based audience captures across three channels

Added an explicit marketing_contact permission basis to new request/selection/page
variants. Existing request/page shapes and legacy lifecycle semantics remain intact;
no retained original or page is rewritten. New variants read current own marketing
contact originals under the same registered-cohort lock/clock and retain them per
customer. All three channels use their independently declared marketing permission;
missing original is unknown, future original unavailable, refusal ineligible. No
fallback to legacy or another channel, no inferred destination/provider authority.
Grant alone is historical audience eligibility; fresh recipient evaluation additionally
requires declared destination and current approval, and still grants no delivery.

New page guard reuses full owned coherent segmentation/profile/cursor checks then
validates exact contact scope/clock/permission/eligibility. Capture and predecessor
pages must agree with original permission basis. Original replay pins basis along
with all other terms; campaign constructor verifies all retained pages/counts as
before. Signed observation/capture routes accept either explicit variant. Two focused
SQLite/actual PostgreSQL tests: 2 passed in 16.08s. Registered 55-customer 50/5 pages,
two retained eligible members, all email/SMS/push DRAFT/REVIEW/APPROVE chains, no
legacy fallback, withdrawal/future new captures, original replay/history unchanged,
forged source scope/permission/basis refusal and signed routes covered.

Full ten non-migration marketing files: 44 passed in 115.78s, terminal exit 0;
existing crypt deprecation only. Native guards/editors do not yet accept/select
new contact-based capture variants; that integration remains required. Legacy native
request shape unchanged. No schema migration, provider call, send receipt or native
acceptance claimed here. All marketing/physical/production gates OPEN; goal ACTIVE.

## 13AB: native contact and audience variant contracts

Frontend contact request/original guards pin own scope, marketing purpose, complete
unique three channels, evidence, channel-specific destination fields, exact actor/
predecessor/reason/key and aware clock. Email shape/control checks complement backend
EmailStr authoritative validation; phone explicit international numeric, push explicit
application/token/length/control. Full terms/actor replay and immutable original
agreement preserve ordered communications, normalize only observation clock spelling.

Audience manifest/catalog guards now accept explicit contact-source variant while
preserving old exact shape. Receipt comparison and retained-page checks pin permission
basis; contact pages validate own original then recompute channel permission and
selected eligibility. Legacy pages retain lifecycle validation/push unsupported.
Wrong/absent basis or source swap refuses; existing source/retained-view components
can consume accepted new variants. Native contact editing and explicit capture-basis
selection are still missing, and no new signed browser acceptance claimed.

Six focused tests: 6 passed in 1.27s. Full frontend: 311 passed in 68.12s, no failures/
skips, terminal exit 0. Final TypeScript/Vite build passes, 139 modules. Actual backend
SQLite fixture export: one legacy plus email/SMS/push captures, four manifests/eight
50/5 pages accepted by native guards with exact predecessor cursors. First extraction
failed parsing diagnostic stdout as JSON; explicit payload prefix fixed extraction,
fixtures cleaned. No new full backend/schema/provider/delivery claim. Next native
contact editor/recovery, contact-source capture choice and signed desktop/tablet
views; then observations/provider/send/conversion. All gates OPEN; goal ACTIVE.

## 13AC: native explicit contact-source audience capture

Capture requires explicit source choice; contacts marketing emits exact new basis,
CRM preserves legacy request. Pending request retains original basis through reload,
verified capture/history displays it. Push explanation separates contact declarations
from legacy email/SMS dimensions. No implicit source default. Visual inspection found
long option clipping on desktop; shortened option names remain readable on both formats.

Final seven focused tests pass in 4.35s: wrong-basis receipt preserves intent, exact
independent reread clears with zero POSTs; prior recovery/session/guard cases remain.
Full frontend: 312 passed in 56.57s, no failures/skips, terminal exit 0 before option-
only wording refinement. Final launcher rebuild passes. Signed Edge desktop/tablet:
initially 2 passed in 53.4s; final refined source options 2 passed in 48.4s, terminal
exit 0, fixtures cleaned. Legacy then push contact-source capture lost replies/reload
recover with two total POSTs per format; exact contact original/source retained,
unknowns excluded, historical legacy original unchanged, pending key clear. Actual
55 then 56 registered cohort pages 50/5 then 50/6 displayed through verified catalog/
key/ID/page checks. Form controls >=44px/no horizontal overflow. Four initial source/
retained-page and two final source screenshots inspected. Existing bcrypt/NO_COLOR,
initial deliberate abort connection reset only. Contacts created by signed fixture
API; native contact editor not yet implemented. No provider/send/new backend/schema
acceptance claimed. Next native contact editor/recovery, observations/provider/send/
conversion. Marketing/physical/production gates OPEN; full canonical goal ACTIVE.

## 13AD: native contact declaration editor and protected recovery

Trusted selected CRM customer now exposes manager contact editor, independent of
transient profile facts. Explicit preparation rereads own current/independent ID and
prefills exact predecessor/terms. Complete three channels/evidence/optional destination
fields, unknown preserved, no inferred customer phone; push token masked. Read-only
signed validate POST checks own customer and returns backend-normalized request.
Canonical email/permissions/destinations shown for explicit confirmation before write;
other full terms/predecessor/key must agree. Final service checks current predecessor.
Full canonical intent stored before original-key lookup/POST; exact actor/full terms,
independent key/ID/current and same stored request precede closure. Advanced head
allowed for immutable old receipt; corrupt reads preserve pending. Session/mount
isolation, invalid-storage freeze, definitive business refusal correction reset.
No original update/delete/provider message.

Five focused editor/contracts tests: 5 passed in 3.23s. Full frontend: 315 passed in
64.18s, no failures/skips, terminal exit 0, including late old-actor reply. Final
TypeScript/Vite launcher build passes, 140 modules. Backend contacts service/pure:
11 passed in 10.32s, actual PostgreSQL cases; preview normalization/no original/key
write and signed role/scope refusal verified. Initial browser two failures were exact
wrapping-label test selector; accessible combobox existed. Corrected accessible-role
selector and bounded action timeout. Final signed desktop/tablet: 2 passed in 40.8s,
terminal exit 0, fixtures cleaned. Three-channel grants/destinations, canonical email
review no write, lost confirmation reply/reload recovery, two mutation POSTs/two
readonly previews per format, exact predecessor withdrawal, email/SMS/old original
unchanged, storage clear. Controls >=44px/no overflow; six screenshots inspected.
Existing bcrypt/NO_COLOR only. No new full backend/schema/provider claim. Next full
native contact/capture/campaign/current-recipient chain, then provider/send/conversion.
Marketing/physical/production gates OPEN; full canonical goal ACTIVE.

## Phase 13AE - native current recipient observations

Explicit manager-only reader mounts beneath verified campaign history; revision/session
change or fresh history clears old observations. Exact page guard recomputes reasons
and current declared eligibility across email/SMS/push, rejects wrong membership/order,
count/scope/digest/clocks and strict authorization flags. Independent campaign current/ID
and per-contact current/ID/key reads must agree before any sampled facts appear.
Changed/withdrawn contacts require a fresh read; no raw addresses/tokens displayed.
Requested offset retained after refusal. Sample is bounded, not browser-held atomic
freshness, complete campaign evaluation, permission to send or provider success.

Initial focused 3 passed in 3.55s. Initial full 317/318 had a test fixed-time assertion
before async digest settled; changed to bounded settled-state wait. Final full frontend
318 passed in 65.46s, zero failures/skips, exit 0. Final focused 4 passed in 3.26s after
21-member last/empty-page boundary coverage. Signed launcher build passes, 142 modules.
Signed Edge desktop/tablet 2 passed in 37.8s; terminal exit 0, fixtures cleaned. API
setup of owned contacts/policy/capture/draft/review/approval; native current recipient
grant then Push withdrawal refusal, corrupt count hides all facts, clean retry.
Prior contact and approved campaign remain exact. Full native authoring chain not
claimed. Buttons >=44px/no overflow, four screenshots inspected. Existing bcrypt/
NO_COLOR diagnostics only. No backend/schema/provider/full-backend acceptance claim.
All marketing/physical/production gates OPEN; canonical goal ACTIVE.

## Phase 13AF - full native contact to campaign approval chain

Expanded existing signed native contact scenario through Push contact-basis audience
capture, source selection, explicit literal IA-declared draft, REVIEW, APPROVE and
current-recipient grant. Registered customer/segment policy alone set up by signed API;
all marketing mutations use native controls. Lost contact reply/reload recovery remains
exactly one original creation. Native correction withdraws Push and fresh recipient read
refuses customer; retained audience page/approval/older contact remain exact. Two contact
POSTs/two readonly previews, one capture POST, three campaign POSTs per format.
No LLM-generated-content claim: fixture text explicitly declared IA-origin. No SEND.

Actual signed Edge desktop/tablet 2 passed in 1.1m (19.2s/19.0s individual), exit 0,
fixtures cleaned. Signed launcher rebuild passes. Four additional chain grant/withdrawal
screenshots inspected. Existing contact 44px/no-overflow checks rerun. Existing bcrypt/
NO_COLOR diagnostics only. Test/docs-only; latest full frontend 318/65.46s from 13AE.
No new backend/schema/provider acceptance. Next delivery provider boundary, durable send
intent/outcome and retained conversion evidence; canonical marketing audit thereafter.
All marketing/physical/production gates OPEN; full canonical goal ACTIVE.

## Phase 13AG - typed delivery provider boundary

Added pure channel-independent submit/reconcile protocol and owned configured-account
terms, including live/test separation and Push application binding. Submission pins
full supplied eligible approved recipient evidence, actor and original operation key;
revalidates nested sources and refuses mismatched/unknown/refused/missing/draft facts.
Canonical exact-term SHA fingerprint normalizes UTC instants but preserves microseconds,
ordered source terms, evidence/content/account/actor/key. Outcome must match exact stored
request account/key/fingerprint and nonbackward clock. Acceptance requires provider
reference; accepted/rejected/unknown never mean recipient delivery. No public endpoint,
credentials, network I/O or fresh-current/enabled-account authority established here.

Six provider tests plus adjacent contacts/campaigns: 21 passed in 0.52s, terminal exit 0.
All channels, source/account/app/mode/key/body/evidence/tamper/time refusals verified.
Test-only fake accepts then loses reply, reconcile/exact retry retains one submission;
changed terms refuse and unseen operation stays unknown. Not live provider acceptance.
Starlette deprecation and intentional malformed-bool serializer warning only. No new
schema/full-backend/frontend/native acceptance. Next durable dispatch intents/outcomes,
current-source preparation, uncertain-I/O recovery, configured adapters/native audit
and retained conversion. All marketing/physical/production gates OPEN; goal ACTIVE.

## Phase 13AH - durable dispatch storage schema

Added intent/outcome/head models and migration 3fa0c198447b. Owned campaign revision
and contact source FKs; one intent per approval/customer, per-institute operation key,
full transport terms/fingerprint/actor/reason/clock retained. Outcome originals and
owned predecessor/current pointer preserve uncertain observations and later results.
SQL source references do not prove approved stage, fresh permissions, provider authority
or JSON semantics. Raw-SQL immutability not claimed; signed services still required.

Initial dual-database 2 passed/12.50s; final 3 passed/28.19s, SQLite/actual PostgreSQL,
exact metadata parity/empty down-up, independent FK failures, duplicate keys/recipient,
self/missing/cross-intent predecessor and wrong head rejected. Old unknown remains when
accepted outcome selected. Retained intents alone block atomic downgrade; offline
explicitly refused. Fifteen older tests change latest-head assertion only.
Full 11 nonmigration marketing files: 50 passed/164.39s, exit 0; actual PostgreSQL
service tests, isolated fixtures clean. All 25 migration files: 52 passed in 351.65s, terminal exit 0, SQLite/actual PostgreSQL. Full run started before final test-case FK isolation; final focused run separately validates that refinement.
Crypt deprecation/intentional provider malformed-bool serialization warning only.
No production migration/new frontend/native/live-provider acceptance. Next signed owned
intent preparation/replay and outcome service, durable uncertain-I/O worker, configured
adapters/native audit/conversion. Marketing/physical/production gates OPEN; goal ACTIVE.

## Phase 13AI - signed owned dispatch intent preparation

Manager-only prepare/key/ID routes; owned institute lock pins current campaign and
contact, evaluates approved membership/current grant/destination with one clock,
resolves server account channel/application and atomically persists exact transport
terms/fingerprint/actor/reason. MARKETING_ACCOUNTS_JSON empty by default; invalid,
absent or ambiguous bindings refuse. Client cannot supply account objects or actor.
Key/full-request/actor replay occurs before fresh sources/config/time; independent
historical approval/contact must equal retained submission. Withdrawal/config removal
preserves historical receipt without authorizing future execution. No provider I/O or
SEND. One operation per approved customer; same-key recovery and competing-key refusal.

Initial 3 passed/15.87s; adjacent preparation/provider/recipient/contact 18 passed/52.20s
before added cases; final 6 preparation tests passed/33.64s, exit 0. Actual PostgreSQL
all three source channels/approvals/intents, withdrawal before any intent creates none,
wrong sources/clock/config refusal, flush rollback, corrupt receipt refusal. Signed
POST/key/ID, actor/term/role/scope/anonymous denial, replay with missing configuration.
Actual PostgreSQL same-key race one identical receipt, distinct keys one winner.
Isolated fixtures clean. Crypt deprecation/deliberate invalid-bool serialization warning
in adjacent provider test only. No schema/full migration/full backend/frontend/native/
live-provider claim. See MARKETING_DISPATCH.md. Next outcome originals, durable
attempt/reconciliation worker, configured adapters/native audit/conversion. All
marketing/physical/production gates OPEN; full canonical goal ACTIVE.

## Phase 13AJ - retained trusted submission outcomes

Internal adapter outcome append binds exact stored intent account/key/fingerprint,
owned current predecessor and worker actor/full replay terms. Nonfuture retention and
monotonic observation clocks, stable known provider reference; unknown may progress,
terminal acceptance/rejection cannot be replaced. Original-key replay before current
head/clock. Atomic original/head rollback, historical unknown retained. Submission
acceptance does not prove recipient delivery or authenticated live provider I/O.

Signed manager readonly current/key/ID/bounded audit; no public write (POST 405).
Role/institute/anonymous denial, cross-intent key/ID refusal, corrupted outcome refuses.
Present predecessor cycles rejected, bounded page does not assert outside full chain.
Initial 4 passed/21.32s; final adjacent outcome/intent/provider 17 passed/57.81s, exit 0,
actual PostgreSQL same-key and competing-key races, stable known reference/terminal/
clock/scope/key semantics and independent owned reads. Final focused outcome file: 5 passed in 27.59s, terminal exit 0, including three-original equal-clock audit cycle refusal.
Crypt deprecation/deliberate malformed-bool serializer warning in adjacent provider
case only. No schema/frontend/native/full-backend/live-provider claim; fixtures clean.
Next durable first-attempt/reconciliation worker with fresh sources/config decisions,
configured adapters/native audit/conversion. See MARKETING_DISPATCH.md. All marketing/
physical/production gates OPEN; canonical goal ACTIVE. No SEND or delivery confirmed.

## Phase 13AK - durable first decision and reconciliation worker

Internal worker resolves exact trusted account/adapter without I/O. First decision
holds owned institute lock, verifies full current approved campaign/contact/registration
and fresh permission/destination clock, commits unknown before provider call. I/O never
holds institute transaction. Existing unknown reconciles only under original key/terms;
terminal returns without provider call. Lost response, malformed result or persistence
failure leaves committed uncertainty recoverable. Missing pointer with retained history
refuses new submit. Latest unknown predecessor retained; conflicting terminal result
refuses replacement. Worker actors are trusted internal identifiers, not public claims.

Initial 5 worker tests passed/98.80s. Final worker/outcome/intent/provider 24 passed/
143.64s, zero failures/skips, exit 0. SQLite/actual PostgreSQL independent connection
sees committed decision before I/O; lost acceptance then withdrawal/reconcile/terminal.
Actual PostgreSQL two workers one submit/one reconcile, no institute lock during waiting
adapter; malformed response/retention rollback recovery, absent config/wrong binding/
failed decision commit no I/O, orphaned history refusal. Crash between committed decision
and submit remains unknown on reconciliation without resubmit or fabricated rejection.
Fixtures clean. Crypt deprecation/intentional malformed-bool serializer warning only.

Decision orders concurrent source corrections; a prior withdrawal prevents submit, a
later correction cannot retract decided bytes or erase uncertain historical acceptance.
Trusted injected fake adapters only: configured real adapters, bounded network behavior,
operator uncertainty resolution and deployed invocation remain. No public execution
route, automatic daemon, live provider, schema/frontend/native/full backend/campaign
SEND/delivery claim. MARKETING_DISPATCH.md updated. Next real adapter/invocation work,
canonical SEND/native audit/conversion. All marketing/physical/production gates OPEN;
full canonical goal ACTIVE.

## Phase 13AL - opt-in SMS/email/Push API adapters

Primary-doc grounded Resend email/Twilio SMS/FCM Push adapters bind exact configured
live account and typed server credential. Exact literal subject/body/destination,
scoped valid UUID/SID/project reference for acceptance, recognized vendor refusal only
for rejection; other responses unknown. Fixed-host verified TLS 1.2+ HTTPS, 10s default
caller deadline/max30, 64KiB bounds, no redirects/proxies/retries. Slow connection stop
prevents late POST; OS DNS thread may finish later, runtime bounds still need acceptance.
Secrets/body hidden from repr; JSON duplicate/nonstandard/oversize refuses.

Resend scoped idempotency header has documented 24h TTL; worker never POSTs during
reconciliation. Existing authoritatively bound references permit exact-message GET
email/SMS, not a new binding inferred from matching recipient alone. Missing reference
and FCM remain unknown; verified callback/reference evidence and operator resolution
still required. No credential acquisition/refresh or deployment activation performed.

Initial focused 13/.63s then 16/.61s pass. First five-file run 35 pass/1 fail/101.53s was
wrongly scoped test assertion NameError; corrected and reran. Final transport/worker/
outcome/intent/provider 37 pass/101.93s, zero failures/skips, exit 0. All wire responses
simulated, no external message sent. Three-channel body/auth/path/reference/refusal,
GET-only known-reference checks, deadline/late-POST/TLS/byte/redirect guards; SQLite
pipeline ack/terminal or lost ack/reconciliation-only unknown. Actual PostgreSQL
adjacent worker/state cases pass, isolated fixtures clean. Crypt deprecation/deliberate invalid
provider-bool warnings only. No schema/frontend/native/full-backend/live-provider/SEND/
delivery claim. See MARKETING_TRANSPORTS.md primary sources/config/deployment limits.
Next credential/invocation wiring, authenticated evidence/operator resolution, SEND/
native audit/conversion. Marketing/physical/production gates OPEN; canonical goal ACTIVE.

## Phase 13AM - trusted transport registry

Empty-by-default server credential bindings now connect exact institute/provider/
account/live-mode metadata to dedicated marketing environment references. Invalid,
ambiguous or foreign bindings refuse. Secrets are reread locally; cached FCM expiry
must exceed the call deadline plus five seconds. No OAuth acquisition, network
lookup, credentials installed or daemon activation. Exception context is suppressed
for invalid configuration. Explicit falsy injected clients never fall back to HTTPS.

Reconciliation reads a retained intent and exact full submission/fingerprint before
using its current outcome reference, in a fresh session after worker transaction
release. Changed actor/terms or unretained keys refuse before simulated GET. This is
trusted retained evidence, not authentication of external provider callbacks.

Initial registry: 6 passed in 5.73s. Six adjacent files: 43 passed in 105.99s.
After final client correction/additional test: registry/transport/provider 26 passed
in 14.14s. All terminal exit 0. Actual PostgreSQL adjacent state/worker tests and
SQLite reference pipeline; simulated wires only. Existing crypt deprecation and
intentional malformed-bool serializer warnings. No new migration/frontend/native/
full-backend or live provider acceptance. All four Phase 13 gates remain OPEN;
canonical SEND authorization/audit, protected invocation, authenticated evidence,
operator uncertainty resolution, conversion and physical/production gates remain.

## Phase 13AN - signed SEND and first worker authorization

Manager-only campaign POST now retains SEND from the exact current APPROVE with
null content, explicit actor/reason/key, immutable content and approval/review
digests. Receipt independently checks owned approved predecessor; atomically
retained original/head rollback and competing keys verified. Key replay preserves
actor/full terms before clock/current head. New SEND duplicate/edit refuse. GET
key/ID/current/audit/catalog support SEND. Stage is a declaration, never delivery.

First worker decision requires current SEND directly following saved exact approval,
unchanged content and nonfuture SEND clock plus current unchanged recipient source
and fresh grant/configuration. Approval alone produces no outcome or provider call.
Unknown recovery remains reconciliation-only; no resend/terminal overwrite.

Backend SEND/campaign/worker/transport/registry 34 passed in 103.82s; catalog/SEND
6 passed in 102.09s; final signed SEND catalog assertion 1 passed in 7.33s. SQLite
and actual PostgreSQL, simulated providers only, existing crypt warning. Full
frontend 320 passed in 70.70s; after final correction-button guard, creator/contracts
11 passed in 2.52s. Initial compilation missing SEND stage mapping corrected;
TypeScript/Vite final build verified. Native contracts/display support SEND and
present predecessor/digest checks; native SEND action/browser acceptance pending.

Preparation currently requires current APPROVE, then SEND precedes execution.
Post-SEND recipient preparation, native intent/results, deployment invocation,
authenticated evidence/operator uncertainty resolution and conversion remain.
No new migration/full-backend/live provider/physical acceptance. All gates OPEN.

## Phase 13AO - native SEND and preparation after SEND

Native manager SEND now uses the verified current approval with explicit reason,
protected institute/actor/campaign request, original key/ID/current recovery plus
independent approved predecessor ID/root/stage/digest/chronology. Lost committed
response survives reload and resumes without another POST. Corrupt approval keeps
pending terms; verified recovery clears them. SEND action performs no provider I/O.
History copy distinguishes authorization from separately verified provider results.

Preparation now accepts the selected current APPROVE or its direct SEND successor.
expected_revision_id remains approval ID, never SEND ID; submissions pin approval
and fresh contact originals. Nonfuture current stage, exact contact, current grant/
destination/account and unique approval/customer intent remain required. No schema
change or new sending endpoint/daemon installed.

Backend four files 19 passed in 94.47s; final expanded new file 2 passed in 11.07s,
SQLite and actual PostgreSQL. Added withdrawal before any intent and renewed explicit
grant cases; wrong SEND/foreign approval/future stage refuse, historical replay
survives later withdrawal. Native action focused 4 passed in 2.47s; full frontend
322 passed in 53.99s before final copy adjustment. Initial signed SEND two browser
cases passed in 36.2s. First combined prior campaign/SEND run 3 passed/1 failed in
3.0m: test assumed target on first catalog page after expansion. Snapshot proved
selection test defect; corrected native bounded pagination. Final combined desktop/
tablet four cases passed in 1.0m, zero failures/skips, terminal exit 0. 142 modules
built, fixture cleaned. Final screenshots inspected, >=44px controls/no overflow.
Existing crypt/bcrypt compatibility/NO_COLOR warnings; no live message acceptance.

Current-recipient observations after SEND, native intent/result audit, invocation,
authenticated provider evidence/operator uncertainty resolution, conversion and
physical/production acceptance remain. No new full-backend/migration acceptance.
All Phase 13 gates OPEN; full canonical goal ACTIVE.

## Phase 13AP - current recipient observations after SEND

SEND is now recognized by the bounded Page stage validator (previous mapping
raised KeyError) and pure permission evaluation. APPROVE/SEND retain reviewed/
approved digest coherence; stage does not override current permission/destination
or future source clock. Read service still pins exact current owned revision and
retained membership, one clock and current contact originals. DB SEND receipt checks
its approved predecessor. Frontend recomputes the same reasons and independently
rereads campaign/contact originals before rendering; forged eligibility hides page.

Five backend files (contacts/recipient/worker/post-SEND preparation/new SEND recipient)
23 passed in 74.42s. Provider adjacent 6 passed in 1.02s. SQLite and actual PostgreSQL,
signed scoped GET, stale approval observation refusal, withdrawal, unchanged SEND/
approval/contact originals and page roundtrip; pure three-channel grant/refusal/
future-clock coverage. Existing crypt and intentional malformed-bool warning only.
Native focused 5 passed in 3.50s; full frontend 323 passed in 57.13s. Signed desktop/
tablet SEND scenario extended to read current grant after SEND, withdraw and reread,
reject forged true eligibility then retry clean: 2 passed in 37.4s. Actual contacts
are explicit API fixtures; native contact editing acceptance remains earlier work.
SEND lost acknowledgement/recovery still one POST. 142 modules built, fixture
cleaned, final screenshots inspected, >=44px controls/no overflow. All terminal
exit 0; no live provider calls or physical/production acceptance inferred.

Native intent preparation/outcome audit, protected invocation, authenticated
provider evidence/operator uncertainty resolution, conversion and canonical
requirement acceptance remain. No new migration/full-backend acceptance. All
Phase 13 gates OPEN; full canonical goal ACTIVE.

## Phase 13AQ - owned dispatch selection catalogs

Manager-only Account metadata GET requires explicit email/sms/push channel and
filters full signed institute/channel scope, with account_id ordering, total/exact
slice, default20/max50. Complete strict configuration parser shared with preparation
and worker; invalid/ambiguous/inline secret entries refuse with suppressed exception
context. No provider connection secrets or credential-binding environment refs.
Listing does not prove configured credentials/provider ownership/live readiness.

Owned campaign intent GET spans retained approvals, bounded created_at/ID order.
Every original validates full submission fingerprint and historical approval/contact
sources. Changed current campaign/account configuration leaves history intact;
corrupt original refuses page. Recipients' declared contact facts remain restricted
to signed manager. Read catalogs do not prepare, dispatch, reconcile or write outcomes.

Catalog/intents/worker/registry 22 passed in 132.13s. Final added fingerprint tamper
whole-page refusal/restore: catalog 2 passed in 15.97s. SQLite and actual PostgreSQL
25 metadata records and 25 historical intents, pages20/5/endempty, exact scopes/order/
originals, zero outcome writes, invalid bounds/config, secret context suppression,
retained intent reads after account removal, signed role/foreign/anonymous refusal.
Terminal exit 0; existing crypt deprecation only. No schema/frontend/native/full-
backend/live provider/physical/production acceptance inferred; native evidence is
13AP. Native contracts/preparation/recovery/result audit, invocation, authenticated
evidence/operator uncertainty resolution, conversion and gate audit remain. All
Phase 13 gates OPEN; full canonical goal ACTIVE.

## Phase 13AR - native dispatch contracts and backend fingerprint vectors

Native strict validators now cover Account selection, requests, retained approved
Submission/Intent and submission Result/Outcome plus bounded pages. Exact scopes,
channel/sender/mode/application, full actor/key/request/source terms, member/grant/
destination and capture clocks checked. SHA-256 uses Python-compatible UTC microsecond
normalization, ASCII Unicode escaping, sorted object keys and original array order;
nonselected channel facts stay bound. Account sort compares Unicode code points.
Receipt matching pins expected actor/request/account; shape validation is not source
authentication or current sending authority. Independent original reads remain needed.

Outcome guards preserve exact intent/account/key/fingerprint, acceptance reference,
strict false delivery flag and observed/retained clocks. Present bounded audit
predecessors refuse cycles, terminal successors, decreasing clocks and changed known
references. Outside-page predecessors are not claimed verified. No worker/UI actions.

Explicit isolated SQLite exporter 1 passed in 6.70s. Checked-in JSON contains three
actual retained backend service chains with Unicode body and fixture-only test
accounts; internal simulated unknown/accepted observations, never provider I/O.
Initial focused8 passed in 0.52s; full frontend331 passed in 51.25s. Final empty scope/
channel guard and nonselected contact/reversed-array test: focused9 passed in 0.52s,
final TypeScript/Vite build142 modules. Full run precedes final narrow extension.
All terminal exit0; exporter crypt warning only. No new browser/full-backend/schema/
live provider/physical/production acceptance. Native preparation/recovery and retained
result readers, invocation, authenticated evidence/operator uncertainty resolution,
conversion and canonical acceptance remain. All Phase 13 gates OPEN; full goal ACTIVE.

## Phase 13AS native protected preparation

PHASE13AS_NATIVE_PROTECTED_PREPARATION:
- Connected manager recipient preparation: explicit bounded account selection pages20/5, visible provider/mode/sender/application, Push application mismatch explanation, explicit reason. Signed exact account metadata GET added; no mount reads or provider calls. Storage scoped institute/actor/campaign/customer contains only Request/Account, no recipient destination/device token. New POST independently verifies current campaign, historical approval, current contact ID/key and selected account; backend remains fresh authority.
- Original-key recovery verifies full actor/request/account/fingerprint and independent intent ID/key, approval/contact originals and owned current campaign before clearing storage. Lost committed reply followed by withdrawal recovers one original without another POST. Forged independent fingerprint retains request. New pre-POST failures clear only newly generated unposted requests; older/uncertain requests freeze. Explicit400/422 permits deliberate exact-storage correction. No worker/outcome writes.
- Backend account/catalog SQLite and actual PostgreSQL: 2 passed15.29s. Final component/recipient focused7 passed9.06s; full frontend337 passed64.08s, zero failures/skips. Final signed native desktop/tablet preparation2 passed53.4s (13.8s/13.0s), build144 modules, owned fixture removed; combined preparation/prior SEND4 passed1.2m before final visual-only assertion extension. Final selection/recovered/withdrawn screenshots inspected on both profiles; preparation controls >=44px and no horizontal overflow asserted. Existing crypt/bcrypt/NO_COLOR warnings only, terminal exit0.
- Development failures resolved before acceptance: mixed Windows text encoding/build failure repaired to strict UTF-8; pre-POST cleanup regression fixed; copied browser keys collided with prior SEND fixtures and now use distinct preparation suffix; missing Push mismatch warning added. Earlier failed runs are not acceptance evidence. Explicit --marketing-fixture installs only owned loopback test-mode metadata, no adapter/credentials; default production configuration unchanged.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full goal ACTIVE. Native retained intent/outcome reader is still needed after storage clearing/audience changes; backend uniqueness already refuses duplicate preparation. NEXT: independently verified retained intent/outcome audit, protected deployed invocation, authenticated provider evidence/operator resolution and retained conversion. No full-backend/schema/migration/live-provider/physical/production acceptance claimed.

## Phase 13AT native retained intent/result audit

Manager campaign pages now expose explicit bounded retained intent reading without
current-recipient loading, independently verified intent ID/key, approved source
and historical contact ID/key, exact current campaign and no destination rendering.
Outcome pages independently read every original/head ID/key and reread current head;
changed or corrupt reads mask results. Present predecessor/head consistency checked,
unknown/refused/accepted/no-result states distinct, accepted is never delivered.
No provider call/outcome write, no outside-page full-history assertion. Token/scope
remount and late reply guards remain. Backend uniqueness still protects preparation;
existing-intent selection in the preparation form remains future UX. All Phase13
gates OPEN; protected invocation/evidence/operator resolution/conversion remain.

- Final component reader2 passed3.45s; full frontend339 passed84.93s, zero failures/skips, terminal exit0. Covers actual backend email retained vectors, unknown/accepted/no-result, forged intent/outcome refusal, head changing between reads, no mount reads/writes, role isolation and late actor response. Initial full339 passed69.21s before final narrow guards/test extensions; final full run includes them. Initial build145 modules passed; later Array.at extension failed the older TypeScript library target and was corrected to indexed access. First browser launch failed before cases on that build; subsequent desktop/tablet cases timed out on test-only French selectors corrupted through PowerShell stdin, now repaired with explicit Unicode escapes. Failed runs are not acceptance evidence.

- Final signed desktop/tablet browser2 passed1.1m (18.7s/14.6s), zero failures/skips, production rebuild succeeds and owned fixture removed. Actual native lost-reply/withdrawal recovery plus retained catalog read independent of current recipients, no-result read, forged independent intent ID masks entire catalog then clean retry, one intent POST retained. Catalog controls >=44px asserted, final catalog screenshots visually inspected desktop/tablet; no horizontal overflow already asserted in same flow. Native accepted/rejected provider outcomes not claimed: those states remain simulated retained service vectors in component tests. Existing bcrypt/NO_COLOR warnings only, terminal exit0. No backend/full-backend/migration/live-provider acceptance in this checkpoint.

## Phase 13AU exact existing recipient intention

PHASE13AU_EXACT_EXISTING_RECIPIENT_INTENT:
- Added manager-only exact owned campaign/APPROVE/customer intent GET with required approval ID. Institute lock, campaign/approved source/customer ownership and full retained receipt/source fingerprint validation; returns original or explicit null. Historical selection independent of current permission/account configuration; absence never grants sending authority. No schema/provider/outcome writes.
- Native preparation now explicitly discovers existing intent and performs this lookup before account choices. Full independent intent ID/key, historical approval/contact ID/key and current selected campaign check. Historical actor may differ from signed manager; protected uncertain request still pins its original actor/full terms and blocks discovery. Found original freezes new preparation without new key/storage/POST; absence cannot enable withdrawn recipient. Failure hides choices, token remount/late guard prevents old publication. Concurrent new creation still protected by backend uniqueness.
- Backend first2 passed24.32s; after wrong-root approval/corrupt fingerprint/missing query assertions, final SQLite+actual PostgreSQL2 passed28.25s, terminal exit0, existing crypt warning only. Includes exact first/latest approval selection, absent own customer, foreign customer, nonapproved revision refusal, history after later edits/config removal, signed roles/anonymous/scope and unchanged intent25/outcome0. Initial focused preparation/history6 passed1 failed because old Push stub returned account page for the new lookup; fixed routing/call-count expectations. Focused9 passed18.74s before final absent/late cases; full first341 passed68.54s, final343 passed75.93s, zero failures/skips, terminal exit0, includes final hide-choices guard and new absent/late tests.
- Final signed native desktop/tablet2 passed1.2m (18.9s/18.5s), zero failures/skips, production rebuild successful and owned fixture removed. Actual explicit discovery after withdrawal and recipient reread returns original, disables new preparation, no protected key and one total intent POST. Existing account20/5 selection/lost-reply/forged independent source/retained audit compatibility preserved. Final existing-intent screenshots inspected on both profiles; controls>=44px and no horizontal overflow assertions in same flow. No native live-provider/accepted-delivery evidence claimed; bcrypt/NO_COLOR compatibility warnings only, terminal exit0.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full goal ACTIVE. NEXT: protected invocation and authenticated provider evidence/operator uncertainty resolution, retained conversion attribution. No full-backend/schema/migration/live-provider/physical/production acceptance claimed.

## Phase 13AV opt-in deployment invocation

PHASE13AV_OPT_IN_DEPLOYMENT_INVOCATION:
- Added standalone single-intent module CLI, required institute/intent/full retained SHA-256. Default inspection reads retained intent/current outcome without credential resolution/I/O/outcome writes. Execution explicit --execute plus exclusive new local receipt; automatic schema creation must be disabled, PostgreSQL exact checked-in Alembic heads, explicitly live retained account. Fixed trusted worker actor and built-in registry only; no credential/actor/adapter CLI options, bulk scan, daemon, scheduling/startup activation/public endpoint or migration.
- Existing worker remains first-decision SEND/contact/permission/account authority and durable-unknown-before-I/O; uncertain reentry reconciles only, terminal no provider I/O. Receipt flush/fsync before stdout, typed redacted summary only (no destination/device/credential/raw exception); no existing file overwrite. Exit0 completed report (acceptance not delivery), exit2 retained unknown report, exit1 failure. Failed local receipt can coexist with committed DB outcome; inspect originals before retry/new receipt, never infer no attempt/no automatic resend.
- Initial invocation PostgreSQL/contract4 passed32.45s, terminal exit0, existing crypt warning only. Actual retained live-mode fixture metadata with fake adapter; offline inspection, wrong fingerprint/owner/missing intent/schema gate, lost reply followed by withdrawal and one-submit/one-reconcile/terminal, exclusive file refusal, unknown/accepted JSON fsynced summaries, failed fsync no secret/raw output/no further calls. Test Alembic stamp is gate fixture on metadata-created owned tables, not deployed migration acceptance. Fresh subprocess CLI --help succeeds. Final invocation/worker/registry3-file regression20 passed127.63s, terminal exit0, zero failures/skips. Added SQLite deployment refusal before resolver, test-mode account refusal before live execution and automatic-schema refusal/withdrawal before decision with zero outcome/provider calls. Existing real PostgreSQL concurrency, commit visibility/outside-lock I/O, crash-before-submit, malformed results, credential rotation/expiry/reference/falsy transport regressions preserved; all external adapters simulated. Existing crypt warning only. No frontend/native/schema/full-backend/live-provider/physical/production acceptance claimed.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full canonical goal ACTIVE. NEXT: authenticated provider evidence/operator uncertainty resolution and retained conversion attribution, production invocation/configuration verification. No credentials installed, external calls or scheduler enabled.

## Phase 13AW explicit billing attribution contracts

PHASE13AW_EXPLICIT_BILLING_ATTRIBUTION_CONTRACTS:
- Added pure manager-link Attribution with full intent/submission fingerprint and request/source binding, unchanged exact owned SEND successor/approval/request, matching accepted outcome and scoped ClosedTicketFact/BillingWindow with one capture and half-open post-observed-acceptance interval. Preparation may precede/follow SEND; both precede provider observation. Typed model_copy inputs revalidated. Exact source actors/chronology required; causality/delivery flags strictly false, numeric/string substitutes refused. No I/O/current execution authority/authentication/database-original proof added.
- Exact campaign/window summaries reject duplicate billing ticket IDs/operation keys across included approvals, separate test/live and CHF/EUR, preserve known/missing/invalid amount diagnostics and unknown currency counts, sum canonical integer minor-unit strings. No FX, fabricated conversion denominator/ROAS/spend/net revenue/causal forecast; rate/ROAS null and complete-history false. Historical declarations do not infer current permission or live delivery.
- Backend fixture is exact checked equality of intent/outcome projection from actual13AR retained three-channel vectors; backend-contained18.9KB avoids frontend mount dependency. SEND/billing windows/tickets and live-mode rehash are explicit synthetic facts, no actual sales attributed/provider calls. Initial collection failed on frontend mount path; projected fixture initially retained a stale institute key lookup, fixed to account scope. First post-SEND test assumed a microsecond before preparation was after approval; fixture clocks were equal, corrected with explicitly later preparation/rehashed observation. Wrong adjacent test filename yielded no cases, corrected. Final conversion/provider/CRM metrics3-file29 passed2.52s; after strict false-flag extension, final conversion6 passed1.15s. Terminal exit0; crypt warning and intentional malformed-bool serializer warning in adjacent provider only. Fixture projection equality independently checked.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full canonical goal ACTIVE. NEXT: durable scoped attribution originals/replay/correction/audit, independently captured paid-ticket sources and signed API/native tracking; authenticated provider evidence/operator uncertainty resolution and production invocation acceptance. No API/frontend/schema/migration/full-backend/live-provider/physical/production acceptance claimed.

## Phase 13AX authoritative attribution preview

PHASE13AX_AUTHORITATIVE_ATTRIBUTION_PREVIEW:
- Added signed manager-only POST conversions/validate with identifiers/fingerprint/window/reason/proposed key only; actor from signed session. Server-owned institute lock and one aware capture, independent intent/SEND/accepted outcome receipt reads plus exact institute/customer recorded paid ticket. Full pure attribution reevaluated, precise CRM minor amount/known-missing-invalid/unknown-currency diagnostics. Wrong recipient/ticket/status/time/fingerprint/SEND/outcome/window refuses; injected actor/ticket/result body objects422. Returned full source terms manager-only, retained:false; no provider call/link write/source update or durable replay claim.
- Explicitly recorded paid billing status/date, not independent settlement proof; preview does not infer causal lift/delivery/current sending authority. Participating billing correction shares institute lock. Old immutable preview does not become a fresh fact and later capture sees changed amount. Proposed key reuse is preview only; future retention must freshly recapture sources and protect original replay.
- Initial source/pure conversion2-file8 passed13.59s, SQLite+actual PostgreSQL, one actual retained fake-adapter SEND/accepted chain and seeded recorded ticket per owned fixture. Selected accepted/intent/SEND exact originals, shared capture, missing/invalid/unknown-currency diagnostics, role/scope/anonymous/body refusal and unchanged intent/outcome counts (one fixture submit, no preview I/O). Audit unknown source selection made status-based because equal-clock IDs do not define chain order. Final source/conversion/CRM billing3-file14 passed33.19s, zero failures/skips, terminal exit0; actual independent PostgreSQL billing writer blocks during pinned preview then new capture reads correction. Existing crypt warning only.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full canonical goal ACTIVE. NEXT: durable scoped attribution originals/replay/correction/audit, signed write/catalog/native tracking; authenticated provider evidence/operator uncertainty resolution and production invocation acceptance. No new schema/migration/frontend/native/full-backend/live-provider/physical/production acceptance claimed.

## Phase 13AY durable conversion schema

PHASE13AY_DURABLE_CONVERSION_SCHEMA:
- Added ConversionOriginal/ConversionHead and additive Alembic4ab1d209558c after3fa0c198447b: full request/attribution JSON/fingerprint, event actor/reason/key/time, linked/retracted action, source intent/campaign authorization/exact intent-outcome pair and billing ticket. Unique institute replay key, one head per institute/ticket, same-ticket predecessor/head composite FKs, distinct predecessor/action/required retraction predecessor checks. Empty down/up supported; online downgrade refuses either retained originals or heads, offline refuses verification-free removal. No append/retract service/API/backfill or semantic paid/accepted/authentication proof from storage alone.
- Source receipt/attribution semantics, customer match, chain transitions/atomic head and append-only application behavior remain future service obligations. Direct admin SQL not made append-only. Invocation's dynamic checked-in-head guard now expects4ab; no deployment migration/config/daemon enabled. Tests use owned disposable SQLite/PostgreSQL schemas and placeholder JSON for structural constraints, not actual conversions.
- Initial new conversion/prior dispatch migration6-case run4 passed2 failed24.40s: new conversion3 and prior offline1 pass; prior dispatch SQLite/Pg fail only stale expected3fa head. Sixteen historical migration test modules now compare exact ScriptDirectory/config graph head instead of stale literals, preserving failed-downgrade unchanged-version proof; new conversion test follows the same graph check. All26-file55-case run49 passed6 failed383.51s: remaining six failures were compact no-space stale-head comparisons in three CRM modules, corrected without product changes. Final affected CRM/new conversion migrations plus invocation/source/pure contracts7-file24 passed107.57s, zero failures/skips, terminal exit0. All six formerly failing migration cases now pass; broad49 plus corrected6 covers all55 cases, not a claimed fresh all55 green run. New schema down/up, exact metadata equality, source/replay/predecessor/action/head constraints and original-only/history/offline refusal verified SQLite/actualPg. Invocation dynamic new-head and retained source previews regressions pass with fake adapters only. After final new-test dynamic graph expectation, focused conversion3 passed13.68s, terminal exit0. Existing crypt warning (and legacy SQLite datetime warning in broad historical invoice test) only. No frontend/native/full-backend/live-provider/physical/production acceptance claimed.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full goal ACTIVE. NEXT: durable source-verified originals/key replay/link/retraction/atomic head/read audit, signed/native conversion tracking; authenticated provider evidence/operator uncertainty resolution and production acceptance.

## Phase 13AZ retained attribution events

PHASE13AZ_RETAINED_ATTRIBUTION_EVENTS:
- Added manager-only linked/retracted POST and key/ID/ticket-current/bounded audit reads. Fresh link recaptures selected authoritative sources under institute lock; explicit retraction copies full linked snapshot; subsequent link freshly captures corrected billing. Request selection ticket/reason/key match outer event terms; signed actor server-derived. Full actor/request original-key replay before current head/clock/source capture, exact expected predecessor for new keys, missing-head with history refusal, atomic original/head flush+commit with rollback.
- UTC canonical complete attribution SHA-256, event/source columns/capture/actor/request bindings, immutable intent/SEND/outcome rereads, entire predecessor ticket/clock/cycle/retraction snapshot proof. Historical price not recaptured after corrections. One head per owned ticket across campaigns; corrections append new events and old originals remain. Verification refuses beyond1000 events rather than partially verifying; audit20/max50 exact total/order/slice, source-proof read budget beyond page count and large-history performance unverified. No provider/outcome writes/causal/delivery/settlement assertion.
- Initial retained events3 passed29.29s SQLite+actualPg; expanded signed POST/link/replay/retract/key reads and source-clock no-recapture assertion, final events/source/pure3-file12 passed56.90s, zero failures/skips, terminal exit0. Actual immutable accepted/SEND fake-adapter chain plus seeded recorded tickets, injected first-head failure leaves zero original/head, amount correction/retract/relink preserves old full receipt, corrupt ancestral fingerprint hides current/audit, missing-pointer new key refusal, role/scope/anonymous denial and actor mismatch. Independent PostgreSQL competing initial keys one winner. After final independent same-key correction/recovery extension, focused retained events3 passed28.49s, terminal exit0: competing first keys one winner, concurrent same full key both return exact same original with only one additional retained event. Existing crypt warning only; no external providers/actual sales attributed.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full goal ACTIVE. NEXT: current-linked campaign conversion catalogs/summaries with complete cohort precision and native protected writer/history; authenticated provider evidence/operator uncertainty resolution and production acceptance. No schema/migration/frontend/native/full-backend/live-provider/physical/production acceptance claimed in this checkpoint.

## Remaining canonical work

Source-backed segmentation/audiences; append-only scoped templates/campaigns and
original-key replay; signed review/approve/send audit; native desktop/tablet UX;
explicit SMS/email/push delivery integration without inferred permissions or
fabricated success; conversion tracking with retained attribution evidence.
Physical/production gates remain separately OPEN. Full canonical goal ACTIVE.

## Phase13BA current conversion cohort

PHASE13BA_CURRENT_CONVERSION_COHORT:
- Added signed manager-only campaign current-conversion catalog and complete current-link summary with explicit aware observed half-open billing window and one server report capture under institute lock. Every historical candidate's current original/full predecessor/source proof validates before publication, even beyond first page or outside window; missing heads, corruption and future events refuse. Current linked events only, retractions and other current campaign assignments excluded; exact ticket-ID ordered pages20/max50. Summary streams all included links, separate test/live currencies, exact minor-unit integer strings and missing/invalid/unknown-currency diagnostics. Historical price unchanged by billing correction alone; explicit new linked event replaces current amount without double counting predecessors.
- Full retained current cohort is not complete sales/conversion/campaign history. Conversion rate/ROAS null, causal/delivery flags false; recorded paid tickets are not settlement proof. Candidate selection trusts retained campaign metadata; no authenticated provider evidence or protection from arbitrary admin SQL claimed. All-candidate proof work is not bounded by page size; large-history performance remains unverified. No native conversion writer/report UI yet.
- Initial catalog2 passed53.00s SQLite+actualPg. Expanded catalog/original/pure run2 failed9 passed81.61s: final test assertion still compared corrected report with pre-correction report; corrected expected value only. Final same3-file11 passed76.82s, zero failures/skips, terminal exit0; existing crypt deprecation warning only. Tests cover 27 links/two retractions/25-current20+5 pages, exact currency diagnostics, empty observed period, off-page/out-of-window corrupted receipt refusal, orphan pointer, actor role/scope/anonymous denial, observed windows/date-only/body bounds, historical billing retention and explicit correction with old original preserved, future current event refusal. Adjacent original replay/atomicity/Pg concurrency and pure summary contracts pass. No new schema/frontend/native/full-backend/live-provider/physical/production acceptance claimed.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full goal ACTIVE. NEXT: native conversion contracts/source selection/protected writer/history/report, authenticated provider evidence/operator uncertainty resolution, then remaining canonical phases and production acceptance.


All four Phase13 functional gates remain OPEN; full canonical goal ACTIVE.

## Phase13BB native conversion contracts

PHASE13BB_NATIVE_CONVERSION_CONTRACTS:
- Added strict native selection/request/preview/attribution/original/current-page/audit-page/report contracts. Reuses full dispatch intent/outcome and campaign digest validators, verifies exact owned SEND successor/unchanged approval, accepted bound outcome, post-acceptance half-open paid-ticket window/shared observed capture, actor/key/source selection and full backend-compatible UTC-microsecond ASCII JSON SHA-256. Literal reasons/messages retained unchanged, alternate timezone representations equal. Retraction retains historical attribution actor while event actor may differ; linked receipt must match protected actor/request and capture. Current pages reject retractions/wrong campaign/window, repeated tickets/IDs/operation keys and wrong ticket-ID ordering. Audit checks present predecessor cycles/chronology/retraction snapshot and unique operation keys; out-of-page ancestors remain unproven without independent reads.
- Report validates observed exact requested window/scope, true retained-current completeness flag with false campaign-history/causal/delivery claims and null rate/ROAS, exact safe counts and live/test currency decomposition, unknown-currency diagnostics, unique ordered groups and canonical arbitrary-precision gross strings using BigInt. Gross cannot exceed known-count times maximum 10-digit ticket minor amount. Structural validity/fingerprint does not authenticate provider evidence or independently prove every cohort original; UI integration must independently fetch originals/sources and handle concurrent report/page captures honestly.
- Opt-in backend exporter1 passed9.38s: actual isolated SQLite retained link/retraction/audit/current page and populated/empty report via authoritative services, seeded recorded paid ticket and fake accepted adapter, no external provider I/O. Native checked-in vector matches exact full backend attribution hash. Initial focused10 passed1609.975ms and build passed; frontend353 passed107716.5646ms, zero failures/skips. After final duplicate-operation/amount-bound guards and tests, focused10 passed1682.1907ms and final TypeScript/production build passed (Vite481ms). Full353 was before final guards; no falsely claimed repeat full run. Tests exercise source/claim/amount substitution refusals, microsecond boundary/offset identity, literal Unicode/date-looking reasons, actor/request recovery bindings, bounded page/chain corruption and amounts above Number precision. Existing backend crypt deprecation warning only.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full goal ACTIVE. No native conversion UI/API wiring/browser/production acceptance claimed. NEXT: source-selection and native protected conversion writer/retraction/history/report with independent source reads; authenticated provider evidence/operator uncertainty resolution; remaining canonical phases and production gates.

## Phase13BC native summary

PHASE13BC_NATIVE_CONVERSION_SUMMARY:
- Added explicit manager-only campaign summary form in the verified campaign history. No mount conversion I/O; positive aware half-open observed window requested explicitly, exact backend report contract checked before display. Displays separate live/test and known currencies, exact BigInt decimal money, missing/invalid amounts and unknown currency diagnostics, historical attribution basis and unproven completeness/delivery/causality with rate/ROAS unavailable. Editing period clears report and invalidates outstanding reads; signed token/role/context/unmount guards suppress stale publication. Generic malformed/server refusal supports retry; no provider or conversion writes.
- Focused UI2 passed3673.6885ms: explicit-only read, invalid dates0calls, exact123.45CHF display, malformed completeness refusal hides old report, non-manager hiding, period/session stale response refusal. TypeScript/production147-module build passed (Vite694ms). Full frontend355 passed68482.7725ms, zero failures/skips, terminal exit0; no native desktop/tablet browser or visual acceptance claimed yet. Explicit ISO timezone text inputs functional but date selection UX still needs refinement and native verification. Protected conversion selection/writer/retraction/audit/current catalog UI remain incomplete.
- CHECKPOINT_STATUS = PARTIAL; all Phase13 gates OPEN, full goal ACTIVE. NEXT: verify native summary desktop/tablet with actual backend and improve date selection, then source selection/protected conversion writer/retraction/history/current catalog; remaining canonical phases and production gates.
