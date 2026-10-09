"""Actual official routing and signed customer services, with no provider."""
from sqlalchemy import event
import app.main as main_module
from app.modules.waitlist.originals import fingerprint
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def setup(client):
    institute, _, _ = _bootstrap_reference_data(client)
    headers = _auth_headers("accueil", institute)
    response = client.post(f"/api/v1/customers/institutes/{institute}", headers=headers,
        json={"display_name": "Cliente test", "phone": "+41000000000", "idempotency_key": "copilot-20a"})
    assert response.status_code in (200, 201), response.text
    return institute, response.json()["id"]


def post(client, institute, customer, message="Consulter la fiche cliente", role="accueil", **extra):
    return client.post("/api/v1/copilot/query", headers=_auth_headers(role, institute),
        json={"message": message, "ui_context": {"customer_id": customer}, **extra})


def test_customer_and_crm_real_sources_no_mutation(client):
    institute, customer = setup(client)
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(main_module.engine, "before_cursor_execute", collect)
    try:
        for message, capability, role in [("Consulter la fiche cliente", "CLIENT_READ", "accueil"),
                ("Resumer le profil CRM cliente", "CLIENT_SUMMARY", "responsable_institut")]:
            response = post(client, institute, customer, message, role)
            assert response.status_code == 200, response.text
            value = response.json()
            assert value["capability"] == capability and value["actions"] == []
            evidence = value["evidence"]
            assert evidence["institute_id"] == institute
            assert evidence["result"]["customer_id"] == customer
            assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
            assert not evidence["complete_customer_history"]
            assert "phone" not in response.text and "+41000000000" not in response.text
            if capability == "CLIENT_SUMMARY":
                assert evidence["result"]["unavailable_reason"] == "policy_absent"
    finally:
        event.remove(main_module.engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}


def test_customer_guards_selection_and_injection(client):
    institute, customer = setup(client)
    assert post(client, institute, customer, "Resumer le profil CRM cliente").status_code == 403
    assert post(client, institute, customer, role="collaboratrice").status_code == 403
    assert post(client, institute, customer, institute_id="foreign").status_code == 422
    assert post(client, institute, customer, capability="CLIENT_SUMMARY").status_code == 422
    assert post(client, institute, "not-owned").status_code == 404
    missing = post(client, institute, None)
    assert missing.status_code == 200 and missing.json()["status"] == "clarification"
    unknown = post(client, institute, customer, "xyzzy unknown intent")
    assert unknown.status_code == 200 and unknown.json()["evidence"] is None


def test_closed_discovery_foreign_scope_and_framework_outage(client, monkeypatch):
    from fastapi import HTTPException
    from sqlalchemy.orm import Session
    from app.modules.base import upstream
    from app.modules.customers.models import Customer
    from app.modules.institutes.models import Institute
    from app.shared.time import utcnow
    institute, customer = setup(client)
    for role, names in [("accueil", ["CLIENT_READ", "PLANNING_READ", "PLANNING_GAPS"]), ("responsable_institut", ["CLIENT_READ", "CLIENT_SUMMARY", "CLIENT_REBOOKING_OPPORTUNITIES", "PLANNING_READ", "PLANNING_GAPS", "EMPLOYEE_CAPACITY", "PLANNING_CONFLICTS", "REVENUE_SUMMARY", "REVENUE_OPPORTUNITIES"])]:
        response = client.get("/api/v1/copilot/capabilities", headers=_auth_headers(role, institute))
        assert response.status_code == 200
        assert [item["name"] for item in response.json()] == names
        assert all(not item["mutates"] for item in response.json())
    with Session(main_module.engine) as db:
        owner = db.get(Institute, institute)
        db.add(Institute(id="copilot-foreign", region_id=owner.region_id, name="Other", city=owner.city, timezone=owner.timezone))
        db.flush()
        db.add(Customer(id="customer_foreign20a", institute_id="copilot-foreign", display_name="Private other",
            phone=None, search_name="private other", phone_digits="", idempotency_key="foreign",
            creation_fingerprint="0" * 64, created_at=utcnow(), created_by=None))
        db.commit()
    for message, role in [("Consulter la fiche cliente", "accueil"), ("Resumer le profil CRM cliente", "responsable_institut")]:
        response = post(client, institute, "customer_foreign20a", message, role)
        assert response.status_code == 404 and "Private other" not in response.text
    def unavailable(*args):
        raise HTTPException(503, "BASE framework unavailable or invalid")
    monkeypatch.setattr(upstream.OfficialRouter, "resolve", unavailable)
    assert post(client, institute, customer).status_code == 503
