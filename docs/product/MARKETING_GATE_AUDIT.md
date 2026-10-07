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

## Remaining canonical work

Source-backed segmentation/audiences; append-only scoped templates/campaigns and
original-key replay; signed review/approve/send audit; native desktop/tablet UX;
explicit SMS/email/push delivery integration without inferred permissions or
fabricated success; conversion tracking with retained attribution evidence.
Physical/production gates remain separately OPEN. Full canonical goal ACTIVE.
