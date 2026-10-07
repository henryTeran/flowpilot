"""Pure campaign review/approval transitions; no transport or delivery authority."""
from hashlib import sha256
import json
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, StringConstraints, model_validator
from app.modules.crm.metrics import Fact, Identifier

Text = Annotated[str, StringConstraints(min_length=1, max_length=10000)]
Actor = Annotated[str, StringConstraints(min_length=1, max_length=160)]
Reason = Annotated[str, StringConstraints(min_length=3, max_length=240)]

class AudienceFact(Fact):
    id: Identifier
    institute_id: Identifier
    captured_at: AwareDatetime
    customer_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def unique_members(self):
        if not self.customer_ids or len(set(self.customer_ids)) != len(self.customer_ids) or any(not value.strip() or value.strip()!=value for value in self.customer_ids):
            raise ValueError("An explicit nonempty unique audience snapshot is required")
        return self

class CampaignContent(Fact):
    institute_id: Identifier
    channel: Literal["sms", "email", "push"]
    origin: Literal["human", "ai"]
    subject: Annotated[str, StringConstraints(min_length=1,max_length=240)] | None
    body: Text
    template_original_id: Identifier | None
    audience: AudienceFact

    @model_validator(mode="after")
    def owned_content(self):
        if self.audience.institute_id != self.institute_id:
            raise ValueError("Campaign and audience must share institute scope")
        if (self.channel == "email") != (self.subject is not None):
            raise ValueError("Email requires a subject; other channels have none")
        if not self.body.strip() or self.subject is not None and not self.subject.strip():
            raise ValueError("Explicit nonblank campaign content required")
        return self

def digest(content: CampaignContent) -> str:
    payload = content.model_dump(mode="json")
    # A snapshot clock's spelling does not change the approved content.
    from datetime import timezone
    payload["audience"]["captured_at"] = content.audience.captured_at.astimezone(timezone.utc).isoformat()
    return sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()

class CampaignRevision(Fact):
    id: Identifier
    campaign_id: Identifier
    institute_id: Identifier
    previous_id: Identifier | None
    state: Literal["DRAFT", "REVIEW", "APPROVE", "SEND"]
    content: CampaignContent
    actor_id: Actor
    reason: Reason
    created_at: AwareDatetime
    reviewed_digest: str | None
    approved_digest: str | None
    external_message_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False

    @model_validator(mode="after")
    def coherent_stage(self):
        expected = digest(self.content)
        if self.institute_id != self.content.institute_id or self.previous_id == self.id or self.content.audience.captured_at > self.created_at:
            raise ValueError("Owned monotonic campaign content and predecessor required")
        if not self.actor_id.strip() or not self.reason.strip():
            raise ValueError("Actor and reason must be explicit")
        if self.state == "DRAFT":
            valid = self.reviewed_digest is None and self.approved_digest is None
        elif self.state == "REVIEW":
            valid = self.reviewed_digest == expected and self.approved_digest is None
        else:
            valid = self.reviewed_digest == expected and self.approved_digest == expected
        if not valid:
            raise ValueError("Review and approval must pin the exact current content/audience")
        return self

def create(identifier: str, campaign: str, content: CampaignContent, actor: str, reason: str, at: AwareDatetime) -> CampaignRevision:
    content = CampaignContent.model_validate(content.model_dump())
    return CampaignRevision(id=identifier,campaign_id=campaign,institute_id=content.institute_id,previous_id=None,state="DRAFT",content=content,actor_id=actor,reason=reason,created_at=at,reviewed_digest=None,approved_digest=None)

def transition(previous: CampaignRevision, expected_revision: str, identifier: str,
               action: Literal["edit", "review", "approve", "send"], actor: str, reason: str,
               at: AwareDatetime, content: CampaignContent | None) -> CampaignRevision:
    previous = CampaignRevision.model_validate(previous.model_dump())
    if expected_revision != previous.id or identifier == previous.id or at < previous.created_at:
        raise ValueError("Exact current revision and monotonic append required")
    if action == "edit":
        if content is None or previous.state == "SEND":
            raise ValueError("Explicit content edit requires an unsent campaign")
        state, reviewed, approved = "DRAFT", None, None
    else:
        if content is not None:
            raise ValueError("A stage transition cannot change approved content")
        required = {"review":"DRAFT", "approve":"REVIEW", "send":"APPROVE"}
        if action not in required or previous.state != required[action]:
            raise ValueError("Campaign must follow DRAFT -> REVIEW -> APPROVE -> SEND")
        content = previous.content
        state = {"review":"REVIEW", "approve":"APPROVE", "send":"SEND"}[action]
        reviewed = digest(content)
        approved = reviewed if state in {"APPROVE", "SEND"} else None
    content = CampaignContent.model_validate(content.model_dump())
    if content.institute_id != previous.institute_id:
        raise ValueError("Campaign institute cannot change")
    return CampaignRevision(id=identifier,campaign_id=previous.campaign_id,institute_id=previous.institute_id,previous_id=previous.id,state=state,content=content,actor_id=actor,reason=reason,created_at=at,reviewed_digest=reviewed,approved_digest=approved)
