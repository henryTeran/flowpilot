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

## Remaining canonical work

Source-backed segmentation/audiences; append-only scoped templates/campaigns and
original-key replay; signed review/approve/send audit; native desktop/tablet UX;
explicit SMS/email/push delivery integration without inferred permissions or
fabricated success; conversion tracking with retained attribution evidence.
Physical/production gates remain separately OPEN. Full canonical goal ACTIVE.
