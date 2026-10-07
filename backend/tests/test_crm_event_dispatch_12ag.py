from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
import app.main as main_module
from app.modules.crm import event_worker, event_ledger
from app.modules.customers.models import Customer
from test_crm_event_worker_12af import prepare
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_crm_billing_12b import NOW

def payload(after=None):return event_worker.PassRequest(after=after,reason="Explicit institute internal pass",idempotency_key="pass")

def exercise(engine,institute,employee,service,monkeypatch):
    prepare(engine,institute,employee,service,monkeypatch)
    factory=sessionmaker(bind=engine)
    first=event_worker.dispatch(factory,institute,payload(),"manager")
    assert all(not item.failed for item in first.items)
    assert "customer_foreign" not in {item.customer_id for item in first.items}
    assert event_worker.dispatch(factory,institute,payload(),"manager")==first
    original_execute=event_ledger.execute
    def fail_one(db,owner,customer,request,actor):
        if customer=="customer_crm":raise RuntimeError("Injected customer failure")
        return original_execute(db,owner,customer,request,actor)
    monkeypatch.setattr(event_ledger,"execute",fail_one)
    partial=event_worker.dispatch(factory,institute,payload(),"manager")
    assert any(i.customer_id=="customer_crm" and i.failed for i in partial.items)
    assert any(i.customer_id=="customer_other" and not i.failed for i in partial.items)

def test_sqlite_dispatch_recovery_failure_isolation_and_signed_scope(client,monkeypatch):
    institute,employees,services=_bootstrap_reference_data(client)
    exercise(main_module.engine,institute,employees[0]["id"],services[0]["id"],monkeypatch)
    path=f"/api/v1/crm/institutes/{institute}/event-worker-pass"
    assert client.post(path,headers=_auth_headers("responsable_institut",institute),json=payload().model_dump()).status_code==200
    for role,owner in (("accueil",institute),("collaboratrice",institute),("responsable_institut","foreign")):
        assert client.post(path,headers=_auth_headers(role,owner),json=payload().model_dump()).status_code==403

def test_postgres_dispatch_receipts_and_failure_isolation(postgres_flow,monkeypatch):exercise(*postgres_flow,monkeypatch)

def test_keyset_scan_covers_more_than_one_page_without_name_search_or_opaque_ids(client,monkeypatch):
    institute,_,_=_bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        for n in range(65):
            db.add(Customer(id=f"dispatch_{n:03}",institute_id=institute,display_name="Same name",search_name="same name",phone=None,phone_digits="",idempotency_key=f"dispatch_{n}",creation_fingerprint="fixture",created_at=NOW,created_by="manager"))
        db.commit()
        expected=set(db.scalars(select(Customer.id).where(Customer.institute_id==institute)))
    calls=[]
    def execute(db,owner,customer,request,actor):calls.append(customer);return SimpleNamespace(id="capture")
    monkeypatch.setattr(event_ledger,"execute",execute)
    after=None
    while True:
        result=event_worker.dispatch(sessionmaker(bind=main_module.engine),institute,payload(after),"manager")
        assert len(result.items)<=50
        if result.next_after is None:break
        after=result.next_after
    assert set(calls)==expected and len(calls)==len(expected)
