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

## Remaining canonical work

Source-backed segmentation/audiences; append-only scoped templates/campaigns and
original-key replay; signed review/approve/send audit; native desktop/tablet UX;
explicit SMS/email/push delivery integration without inferred permissions or
fabricated success; conversion tracking with retained attribution evidence.
Physical/production gates remain separately OPEN. Full canonical goal ACTIVE.
