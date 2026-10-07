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

## Remaining canonical work

Source-backed segmentation/audiences; append-only scoped templates/campaigns and
original-key replay; signed review/approve/send audit; native desktop/tablet UX;
explicit SMS/email/push delivery integration without inferred permissions or
fabricated success; conversion tracking with retained attribution evidence.
Physical/production gates remain separately OPEN. Full canonical goal ACTIVE.
