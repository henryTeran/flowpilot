"""Official BASE preparation of a literal template-bound draft; no contact authority."""
from typing import Literal
from pydantic import AwareDatetime, model_validator
from fastapi import HTTPException
from app.modules.crm.metrics import Fact, Count
from app.modules.base import query, upstream, audit, read_capabilities as base
from app.modules.base.plans import guard, Reason, Key
from app.modules.marketing import campaign_originals as originals, templates, campaigns
from app.modules.waitlist.originals import fingerprint


class Selection(Fact):
    audience_id: base.ExactId
    template_original_id: base.ExactId


class PreviewRequest(Fact):
    message: query.Text
    ui_context: Selection


class Request(PreviewRequest):
    expected_state_fingerprint: base.Digest
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def exact_terms(self):
        if any(value != value.strip() or any(ord(c) < 32 for c in value) for value in (self.reason, self.idempotency_key)):
            raise ValueError("Exact reviewed reason and recovery key required")
        return self


class Preview(Fact):
    principal: base.Principal
    capability: Literal["MARKETING_CAMPAIGN_DRAFT"] = "MARKETING_CAMPAIGN_DRAFT"
    selection: Selection
    captured_at: AwareDatetime
    channel: Literal["sms", "email", "push"]
    recipient_count: Count
    state_fingerprint: base.Digest
    effect: Literal["draft_preview_only_no_campaign_approval_contact_or_delivery"] = "draft_preview_only_no_campaign_approval_contact_or_delivery"


class Draft(Fact):
    principal: base.Principal
    capability: Literal["MARKETING_CAMPAIGN_DRAFT"] = "MARKETING_CAMPAIGN_DRAFT"
    selection: Selection
    original_id: base.ExactId
    campaign_id: base.ExactId
    created_at: AwareDatetime
    channel: Literal["sms", "email", "push"]
    recipient_count: Count
    state: Literal["DRAFT"] = "DRAFT"
    state_fingerprint: base.Digest
    original_fingerprint: base.Digest
    effect: Literal["retained_draft_only_no_campaign_approval_contact_or_delivery"] = "retained_draft_only_no_campaign_approval_contact_or_delivery"


class Capability(Fact):
    name: Literal["MARKETING_CAMPAIGN_DRAFT"] = "MARKETING_CAMPAIGN_DRAFT"
    level: Literal[2] = 2
    permission: Literal["signed_institute_manager"] = "signed_institute_manager"
    input_schema: dict = Request.model_json_schema()
    preview_input_schema: dict = PreviewRequest.model_json_schema()
    output_schema: dict = Draft.model_json_schema()
    application_service: Literal["marketing.campaign_originals.execute_create_only"] = "marketing.campaign_originals.execute_create_only"
    audit: Literal["signed_scope_interaction_id_and_source_digest_no_raw_message"] = "signed_scope_interaction_id_and_source_digest_no_raw_message"
    effect: Literal["retained_draft_only_no_campaign_approval_contact_or_delivery"] = "retained_draft_only_no_campaign_approval_contact_or_delivery"


def route(message, router=None):
    if not message.strip():raise HTTPException(400, "An explicit draft request is required")
    resolved = upstream.Route.model_validate((router or upstream.OfficialRouter()).resolve(message).model_dump())
    if resolved.status != "routed" or resolved.process_id != "marketing-campaign-draft":
        raise HTTPException(400, "BASE must route to the selected draft capability")


def payload(db, institute, selection, reason, key):
    template = templates.require(db, institute, selection.template_original_id).content
    content = originals.Content(channel=template.channel, origin=template.origin, subject=template.subject,
        body=template.body, audience_id=selection.audience_id, template_original_id=selection.template_original_id)
    return originals.Request(action="create", campaign_id=None, expected_revision_id=None,
        content=content, reason=reason, idempotency_key=key)


def preview(db, principal, candidate, router=None):
    principal = guard(principal, principal.institute_id)
    request = PreviewRequest.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, PreviewRequest) else candidate)
    with audit.trace(principal, "copilot_marketing_preview", request.model_dump(mode="json")) as span:
        route(request.message, router)
        result = originals.preview_creation(db, principal.institute_id,
            payload(db, principal.institute_id, request.ui_context, "Preview selected draft", "preview-only"), principal.actor_id)
        response = Preview(principal=principal, selection=request.ui_context, captured_at=result.captured_at,
            channel=result.content.channel, recipient_count=len(result.content.audience.customer_ids), state_fingerprint=result.content_digest)
        span.result("previewed", response.capability, response.state_fingerprint)
        return response


def prepare(db, principal, candidate, router=None):
    principal = guard(principal, principal.institute_id)
    request = Request.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, Request) else candidate)
    with audit.trace(principal, "copilot_marketing_prepare", request.model_dump(mode="json")) as span:
        route(request.message, router)
        old = originals.original(db, principal.institute_id, request.idempotency_key)
        if old is not None:
            terms = old.request
            if (terms.action != "create" or old.revision.actor_id != principal.actor_id
                or terms.reason != request.reason or terms.content.audience_id != request.ui_context.audience_id
                or terms.content.template_original_id != request.ui_context.template_original_id
                or campaigns.digest(old.revision.content) != request.expected_state_fingerprint):
                raise HTTPException(400, "Draft key retains exact actor, sources and terms")
            result = old
        else:
            terms = payload(db, principal.institute_id, request.ui_context, request.reason, request.idempotency_key)
            observed = originals.preview_creation(db, principal.institute_id, terms, principal.actor_id)
            if observed.content_digest != request.expected_state_fingerprint:
                raise HTTPException(400, "Draft sources differ from the reviewed preview")
            result = originals.execute(db, principal.institute_id, terms, principal.actor_id)
        revision = result.revision
        response = Draft(principal=principal, selection=request.ui_context, original_id=revision.id,
            campaign_id=revision.campaign_id, created_at=revision.created_at, channel=revision.content.channel,
            recipient_count=len(revision.content.audience.customer_ids), state_fingerprint=campaigns.digest(revision.content),
            original_fingerprint=fingerprint(result.model_dump(mode="json")))
        span.result("retained_draft", response.capability, response.original_fingerprint)
        return response
