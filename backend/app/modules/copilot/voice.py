"""Voice intent preview. Transcription and routing never execute domain actions."""
from typing import Literal
import hashlib
from pydantic import model_validator
from fastapi import HTTPException
from app.ai import boundary, contracts
from app.modules.base import upstream
from app.modules.base.plans import guard
from app.modules.crm.metrics import Fact
from app.modules.base.read_capabilities import Principal

class Preview(Fact):
    principal: Principal
    transcript: str
    route: upstream.Route | None
    status: Literal["review_required", "silent"]
    effect: Literal["transcript_intent_only_no_domain_action"] = "transcript_intent_only_no_domain_action"

    @model_validator(mode="after")
    def bound_intent(self):
        if self.status == "silent":
            if self.transcript.strip() or self.route is not None:
                raise ValueError("Silence must not contain a route")
        elif not self.transcript.strip() or len(self.transcript) > 2000 or self.route is None:
            raise ValueError("Bounded nonempty transcript and route required")
        elif self.route.request_digest != hashlib.sha256(self.transcript.encode("utf-8")).hexdigest():
            raise ValueError("Route must bind exact transcript")
        elif self.route.status == "routed" and (not self.route.process_id or not self.route.context_prepared):
            raise ValueError("Routed intent requires prepared process context")
        elif self.route.status == "clarification" and (self.route.process_id is not None or self.route.context_prepared):
            raise ValueError("Clarification must not grant process context")
        return self


def preview(principal, audio, provider, router=None):
    guard(principal, principal.institute_id)
    request = boundary.validated(contracts.AudioRequest, audio)
    if provider is None:
        raise HTTPException(503, "Speech transcription unavailable")
    try:
        transcript = boundary.transcribe(provider, request).text
    except (boundary.ProviderUnavailable, boundary.InvalidProviderResponse) as error:
        raise HTTPException(503, "Speech transcription unavailable or invalid") from error
    if not transcript.strip():
        return Preview(principal=principal, transcript=transcript, route=None, status="silent")
    if len(transcript) > 2000:
        raise HTTPException(422, "Transcript exceeds supported intent length")
    route = (router or upstream.OfficialRouter()).resolve(transcript)
    try:
        return Preview(principal=principal, transcript=transcript, route=route, status="review_required")
    except ValueError as error:
        raise HTTPException(503, "BASE voice intent unavailable or invalid") from error
