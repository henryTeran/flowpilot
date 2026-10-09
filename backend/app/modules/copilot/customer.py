from types import MappingProxyType
from typing import Literal
from fastapi import HTTPException
from pydantic import AwareDatetime
from app.modules.base import audit, query, upstream, read_capabilities as identity
from app.modules.crm import profile
from app.modules.crm.metrics import Fact
from app.modules.customers.repository import require_customer
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow, explicit_utc_instant

Name = Literal["CLIENT_READ", "CLIENT_SUMMARY"]
PROCESSES = MappingProxyType({"client-read": "CLIENT_READ", "client-summary": "CLIENT_SUMMARY"})


class Selection(Fact):
    customer_id: identity.ExactId | None = None


class Request(query.Request):
    ui_context: Selection = Selection()


class CustomerFacts(Fact):
    customer_id: identity.ExactId
    institute_id: identity.ExactId
    display_name: str
    created_at: AwareDatetime


class Capability(Fact):
    name: Name
    level: Literal[0] = 0
    permission: Literal["customer_operator", "crm_manager"]
    input_schema: dict
    output_schema: dict
    application_service: str
    mutates: Literal[False] = False


REGISTRY = MappingProxyType({name: Capability(name=name, permission=permission,
    input_schema=Selection.model_json_schema(), output_schema=output.model_json_schema(),
    application_service=service) for name, permission, output, service in (
        ("CLIENT_READ", "customer_operator", CustomerFacts, "customers.repository.require_customer"),
        ("CLIENT_SUMMARY", "crm_manager", profile.SegmentProfile, "crm.profile.read"))})


class Evidence(Fact):
    capability: Name
    institute_id: identity.ExactId
    captured_at: AwareDatetime
    read_completed_at: AwareDatetime
    result: CustomerFacts | profile.SegmentProfile
    fingerprint: identity.Digest
    integrity: Literal["response_sha256_not_signature_or_retained_original"] = "response_sha256_not_signature_or_retained_original"
    complete_customer_history: Literal[False] = False


class Response(Fact):
    request_id: str
    status: Literal["answered", "clarification"]
    answer: str
    capability: Name | None = None
    evidence: Evidence | None = None
    actions: tuple[()] = ()
    framework: Literal["ai-swiss/base@1.5.1"] = "ai-swiss/base@1.5.1"


def read(db, principal, candidate, router=None):
    principal = query.guard(principal, principal.institute_id)
    request = Request.model_validate(candidate.model_dump() if isinstance(candidate, Request) else candidate)
    with audit.trace(principal, "copilot_customer_query", request.model_dump(mode="json")) as span:
        route = upstream.Route.model_validate((router or upstream.OfficialRouter()).resolve(request.message).model_dump())
        name = PROCESSES.get(route.process_id) if route.status == "routed" else None
        if name == "CLIENT_SUMMARY" and principal.role != "responsable_institut":
            raise HTTPException(403, "CRM summary requires institute manager")
        if name is None or request.ui_context.customer_id is None:
            response = Response(request_id=span.id, status="clarification", capability=name,
                answer="Sélectionnez une cliente et demandez sa fiche ou son résumé CRM.")
        else:
            captured = utcnow()
            if name == "CLIENT_READ":
                row = require_customer(db, principal.institute_id, request.ui_context.customer_id)
                result = CustomerFacts(customer_id=row.id, institute_id=row.institute_id,
                    display_name=row.display_name, created_at=explicit_utc_instant(row.created_at))
                answer = "Identité enregistrée de la cliente sélectionnée."
            else:
                result = profile.read(db, principal.institute_id, request.ui_context.customer_id, _captured_at=captured)
                answer = "Profil CRM observé selon la politique enregistrée; historique complet indisponible."
                if result.unavailable_reason:
                    answer = "Segment CRM indisponible : " + result.unavailable_reason + "."
            evidence = Evidence(capability=name, institute_id=principal.institute_id,
                captured_at=captured, read_completed_at=utcnow(), result=result, fingerprint="0" * 64)
            evidence = evidence.model_copy(update={"fingerprint": fingerprint(evidence.model_dump(mode="json", exclude={"fingerprint"}))})
            response = Response(request_id=span.id, status="answered", answer=answer, capability=name, evidence=evidence)
        span.result(response.status, response.capability, response.evidence.fingerprint if response.evidence else None)
        return response
