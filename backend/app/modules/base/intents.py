"""Language proposes a capability; signed explicit selections remain authority."""
from typing import Annotated, Literal, Protocol
from types import MappingProxyType
from unicodedata import combining, normalize
from fastapi import HTTPException
from pydantic import Field, StringConstraints, model_validator
from app.modules.base import read_capabilities as base
from app.modules.crm.metrics import Fact
from app.modules.waitlist.originals import fingerprint

Utterance = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2000)]


class Request(Fact):
    utterance: Utterance
    selections: Annotated[tuple[base.Invocation, ...], Field(max_length=20)] = ()

    @model_validator(mode="after")
    def explicit_language(self):
        if not self.utterance.strip() or any(ord(c) < 32 and c not in "\n\t\r" for c in self.utterance):
            raise ValueError("A nonempty language request without control characters is required")
        digests = [fingerprint(s.model_dump(mode="json")) for s in self.selections]
        if len(digests) != len(set(digests)):
            raise ValueError("Duplicate selections do not disambiguate an intent")
        return self


class Proposal(Fact):
    status: Literal["recognized", "clarification", "unsupported"]
    capabilities: Annotated[tuple[base.Name, ...], Field(max_length=3)] = ()

    @model_validator(mode="after")
    def coherent(self):
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("Distinct proposed capabilities required")
        if self.status == "recognized" and len(self.capabilities) != 1:
            raise ValueError("Recognition requires exactly one proposed capability")
        if self.status == "unsupported" and self.capabilities:
            raise ValueError("Unsupported language cannot propose a capability")
        return self


class Interpreter(Protocol):
    def propose(self, utterance: str, allowed: tuple[base.Name, ...]) -> Proposal:
        """No DB, actor, selected references or executable arguments are provided."""
        ...


class LocalInterpreter:
    """Conservative whole-utterance grammar, not a general language/LLM claim.

    Unrecognized wording, negation, mixed actions and instructions are clarified;
    substring detection never turns an arbitrary sentence into a tool call.
    """
    phrases = MappingProxyType({
        "WAITLIST_READ": ("lire la liste d'attente", "afficher la liste d'attente", "consulter la liste d'attente", "read the waitlist", "show the waitlist"),
        "WAITLIST_MATCH": ("chercher des creneaux pour la liste d'attente", "trouver des creneaux pour la liste d'attente", "examiner les creneaux de la liste d'attente", "find slots for the waitlist"),
        "PLANNING_OPTIMIZATION": ("optimiser le planning", "comparer les scores du planning", "calculer les scores du planning", "optimize the schedule", "score the schedule"),
    })

    def propose(self, utterance, allowed):
        text = "".join(c for c in normalize("NFKD", utterance.casefold().replace("’", "'")) if not combining(c))
        text = " ".join(text.split()).rstrip(".?!").rstrip()
        for prefix in ("peux-tu ", "peux tu ", "merci de ", "merci d'", "can you ", "please "):
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        for name, phrases in self.phrases.items():
            if name in allowed and text in phrases:
                return Proposal(status="recognized", capabilities=(name,))
        return Proposal(status="clarification")


class Resolution(Fact):
    status: Literal["ready", "clarification", "unsupported"]
    reason: Literal["explicit_selection_ready", "language_requires_clarification", "unsupported_intent", "selection_required", "multiple_selected_references"]
    principal: base.Principal
    proposal: Proposal
    context: base.Context | None = None
    invocation: base.Invocation | None = None
    request_fingerprint: base.Digest
    effect: Literal["intent_selection_only_no_business_read_or_execution"] = "intent_selection_only_no_business_read_or_execution"


def resolve(principal: base.Principal, institute: str, candidate, interpreter: Interpreter | None = None):
    # Revalidate typed copies as well as raw boundary values, before any provider.
    try:
        principal = base.Principal.model_validate(principal.model_dump())
        allowed = tuple(c.name for c in base.capabilities(principal, institute))
        if not allowed:
            raise ValueError("No permitted intent capabilities")
    except (ValueError, TypeError, AttributeError) as error:
        raise HTTPException(403, "BASE intent scope not authorized") from error
    try:
        request = Request.model_validate(candidate.model_dump() if isinstance(candidate, Request) else candidate)
    except (ValueError, TypeError) as error:
        raise HTTPException(400, "BASE requires an explicit language request and selections") from error
    selections = tuple(base.resolve(principal, institute, s) for s in request.selections)
    try:
        proposed = (interpreter or LocalInterpreter()).propose(request.utterance, allowed)
        proposal = Proposal.model_validate(proposed.model_dump() if isinstance(proposed, Proposal) else proposed)
        if any(name not in allowed for name in proposal.capabilities):
            raise ValueError("Provider proposed an unauthorized capability")
    except Exception as error:
        # Never use malformed/provider-failed output as a fallback executable intent.
        raise HTTPException(502, "BASE language interpretation unavailable or invalid") from error
    matched = tuple(s for s in selections if proposal.status == "recognized" and s[1].capability == proposal.capabilities[0])
    status, reason, context, invocation = "clarification", "language_requires_clarification", None, None
    if proposal.status == "unsupported":
        status, reason = "unsupported", "unsupported_intent"
    elif proposal.status == "recognized":
        if len(matched) == 1:
            status, reason = "ready", "explicit_selection_ready"
            context, invocation = matched[0]
        else:
            reason = "selection_required" if not matched else "multiple_selected_references"
    return Resolution(status=status, reason=reason, principal=principal, proposal=proposal,
        context=context, invocation=invocation, request_fingerprint=fingerprint(request.model_dump(mode="json")))
