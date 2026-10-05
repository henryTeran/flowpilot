from test_ticket_workflow import _auth_headers, _bootstrap_reference_data
from test_loyalty_foundation_8q import customer
import app.main as main_module


def test_scoped_snapshot_matches_ledger_and_reversal_history(client):
    institute, employees, services = _bootstrap_reference_data(client)
    identity = customer(main_module.engine, institute)
    root = f"/api/v1/loyalty/institutes/{institute}/customers/{identity}"
    operator, manager = _auth_headers(institute_id=institute), _auth_headers("responsable_institut", institute)
    for headers in (_auth_headers(institute_id=None), _auth_headers(institute_id="other"), _auth_headers("collaboratrice", institute)):
        assert client.get(root + "/snapshot", headers=headers).status_code == 403
    assert client.get(root + "/snapshot", headers=operator).json() == dict(balance=dict(customer_id=identity, points=0, tier=None), entries=[], redemptions=[])
    payload = dict(points=30, reason="Correction explicite", idempotency_key="credit")
    assert client.post(root + "/adjustments", headers=manager, json=payload).status_code == 200
    snapshot = client.get(root + "/snapshot", headers=operator)
    assert snapshot.status_code == 200
    facts = snapshot.json()
    assert facts["balance"]["points"] == sum(row["points"] for row in facts["entries"]) == 30
    assert facts["entries"] == client.get(root + "/history", headers=operator).json()
    assert client.get(f"/api/v1/loyalty/institutes/{institute}/customers/missing/snapshot", headers=operator).status_code == 404


from test_postgres_scheduling_4d import postgres_flow, race


def test_snapshot_serializes_with_point_writer(postgres_flow):
    from types import SimpleNamespace
    from app.modules.loyalty.routes import customer_snapshot
    from app.modules.loyalty.service import adjust
    from app.modules.loyalty.schemas import AdjustmentCreate
    engine, institute, employee, care = postgres_flow
    identity = customer(engine, institute)
    snapshots = []
    def read(db):
        facts = customer_snapshot(institute, identity, user={}, db=db)
        # Materialize before releasing the lock, as response serialization does.
        snapshots.append((facts["balance"]["points"], sum(row.points for row in facts["entries"])))
        return SimpleNamespace(id="snapshot")
    results = race(engine, [read, lambda db: adjust(db, institute, identity,
        AdjustmentCreate(points=5, reason="Concurrent correction", idempotency_key="credit"), "manager")])
    assert all(row[0] == "ok" for row in results)
    assert snapshots in ([(0,0)], [(5,5)])
