"""Voice intent preview. Transcription and routing never execute domain actions."""
from typing import Literal
from fastapi import HTTPException
from app.ai import boundary, contracts
from app.modules.base import upstream
from app.modules.base.plans import guard
from app.modules.crm.metrics import Fact

class Preview(Fact):
    transcript: str
    route: upstream.Route | None
    status: Literal["review_required", "silent"]
    effect: Literal["transcript_intent_only_no_domain_action"] = "transcript_intent_only_no_domain_action"


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
        return Preview(transcript=transcript, route=None, status="silent")
    if len(transcript) > 2000:
        raise HTTPException(422, "Transcript exceeds supported intent length")
    route = (router or upstream.OfficialRouter()).resolve(transcript)
    return Preview(transcript=transcript, route=route, status="review_required")
