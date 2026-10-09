"""Capture through signed BASE services before deterministic JV analysis."""
import logging
from fastapi import HTTPException
from app.modules.base import query
from app.modules.crm.metrics import Fact
from app.modules.jv.operational import OperationalAnalysis, OperationalAnalyzer

logger = logging.getLogger("app.modules.jv.service")


class Response(Fact):
    source: query.Response
    analysis: OperationalAnalysis | None


def analyze_query(db, principal, request: query.Request) -> Response:
    source = query.query(db, principal, principal.institute_id, request)
    if source.evidence is None:
        return Response(source=source, analysis=None)
    fields = dict(audit_operation_id=source.request_id, audit_actor_id=principal.actor_id,
        audit_institute_id=principal.institute_id, audit_action="jv_operational_analysis",
        audit_evidence_digest=source.evidence.fingerprint)
    try:
        analysis = OperationalAnalyzer().analyze(source.evidence)
    except ValueError as error:
        logger.info("JV analysis", extra={**fields, "audit_status": "invalid_source"})
        raise HTTPException(503, "JV source evidence invalid") from error
    logger.info("JV analysis", extra={**fields, "audit_status": "completed", "audit_analysis_digest": analysis.fingerprint})
    return Response(source=source, analysis=analysis)
