from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


def test_assignment_options_api_respects_reservations(client):
    institute, employees, services = _bootstrap_reference_data(client)
    headers = _auth_headers(institute_id=institute)
    first = _create_ticket(client, institute, services[0]["id"])
    second = _create_ticket(client, institute, services[0]["id"])
    employee = employees[0]["id"]
    path = f"/api/v1/availability/{second['id']}/assignment-options?institute_id={institute}"
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    assert next(o for o in response.json()["options"] if o["employee_id"] == employee)["assignable"]
    assigned = client.patch(f"/api/v1/tickets/{first['id']}/assign", headers=headers, json={"employee_id": employee})
    assert assigned.status_code == 200
    option = next(o for o in client.get(path, headers=headers).json()["options"] if o["employee_id"] == employee)
    assert not option["assignable"]
    assert option["reason"] == "employee_reserved"
    assert option["projected_end_time"] is None


def test_scheduling_api_auth_tenant_and_missing_ticket(client):
    institute, employees, services = _bootstrap_reference_data(client)
    ticket = _create_ticket(client, institute, services[0]["id"])
    path = f"/api/v1/availability/{ticket['id']}/assignment-options?institute_id={institute}"
    assert client.get(path).status_code == 403
    assert client.get(path, headers=_auth_headers("collaboratrice", institute)).status_code == 403
    assert client.get(path, headers=_auth_headers(institute_id="other")).status_code == 403
    foreign = f"/api/v1/availability/{ticket['id']}/assignment-options?institute_id=other"
    assert client.get(foreign, headers=_auth_headers(institute_id="other")).status_code == 404
    missing = f"/api/v1/availability/missing/assignment-options?institute_id={institute}"
    assert client.get(missing, headers=_auth_headers(institute_id=institute)).status_code == 404
    availability = f"/api/v1/availability/employees/{employees[0]['id']}?institute_id={institute}"
    assert client.get(availability, headers=_auth_headers(institute_id=institute)).status_code == 200
    pool = f"/api/v1/availability/institutes/{institute}/pool"
    assert client.get(pool, headers=_auth_headers(institute_id=institute)).status_code == 200
