"""Owned loopback browser-test backend; never uses an existing database."""
import os
import json
import argparse
from pathlib import Path
import secrets
import sys
from tempfile import gettempdir

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate-payments", action="store_true")
    options = parser.parse_args()
    directory = Path(os.environ["FLOWPILOT_BROWSER_DIRECTORY"]).resolve()
    if (directory.parent != Path(gettempdir()).resolve()
            or not directory.name.startswith("flowpilot-browser-")
            or not (directory / ".flowpilot-browser-owner").is_file()):
        raise RuntimeError("Owned browser fixture directory required")
    database = directory / "browser.sqlite"
    if database.exists():
        raise RuntimeError("Refusing to open an existing browser fixture database")
    os.environ.update(
        DATABASE_URL="sqlite:///" + database.as_posix(), APP_ENV="test",
        SECRET_KEY=secrets.token_urlsafe(48), APP_DEBUG="false",
        AUTO_CREATE_SCHEMA_ON_STARTUP="false", CORS_ORIGINS="http://127.0.0.1:4199",
        RATE_LIMIT_AUTH_MAX_REQUESTS="20", PYTHONDONTWRITEBYTECODE="1",
    )
    sys.dont_write_bytecode = True
    from app.main import app, create_app
    from app.database.base import Base
    from app.database.session import engine
    from app.core.security import hash_password
    from app.modules.auth.models import User
    from app.modules.dev.routes import init_demo_data, DEMO_INSTITUTE_ID
    from app.modules.resources.models import Resource, ResourceRequirement
    from sqlalchemy.orm import Session
    import uvicorn

    if os.environ.get("FLOWPILOT_BROWSER_MARKETING_FIXTURE") == "1":
        from app.core.config import settings
        # Metadata-only test accounts in this owned loopback database. No adapter or credentials.
        accounts = [dict(institute_id=DEMO_INSTITUTE_ID, provider="fixture-only", account_id="browser-test-account", channel=channel,
            sender_id="fixture-sender", mode="test", push_application="institute-app" if channel == "push" else None)
            for channel in ("email", "sms", "push")]
        accounts += [{**accounts[0], "account_id":f"browser-account-{index:02}"} for index in range(24)]
        settings.MARKETING_ACCOUNTS_JSON = json.dumps(accounts)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        init_demo_data(db)
        # Explicit fixture capacity: two qualified staff share one treatment room.
        db.add(Resource(id="browser-room", institute_id=DEMO_INSTITUTE_ID,
                        name="Browser shared room", kind="room", capabilities=[], status="active"))
        db.add(ResourceRequirement(id="browser-room-need", institute_id=DEMO_INSTITUTE_ID,
                                   service_id="svc-soin-profond", kind="room", capability="", quantity=1))
        for role, name in (("responsable_institut", "manager"), ("responsable_institut", "manager-peer"), ("accueil", "cashier")):
            db.add(User(id="browser-" + name, email=name + "@browser.example.com",
                        password_hash=hash_password("Browser-test-only-2026"),
                        role=role, institute_id=DEMO_INSTITUTE_ID, status="active"))
        db.commit()
    if os.environ.get("FLOWPILOT_BROWSER_CONVERSION_FIXTURE") == "1":
        from conversion_fixture import seed_conversion
        manifest = seed_conversion(engine, DEMO_INSTITUTE_ID)
        @app.get("/_fixture/conversion")
        def conversion_manifest():
            return manifest
    if os.environ.get("FLOWPILOT_BROWSER_CRM_HISTORY_FIXTURE") == "1":
        from crm_history_fixture import seed_history
        history_manifest = seed_history(engine, DEMO_INSTITUTE_ID)
        @app.get("/_fixture/crm-history")
        def crm_history_manifest():
            return history_manifest
    if os.environ.get("FLOWPILOT_BROWSER_PLANNING_FIXTURE") == "1":
        from planning_fixture import seed_planning, read_snapshot
        planning_manifest = seed_planning(engine, DEMO_INSTITUTE_ID)
        @app.get("/_fixture/planning")
        def planning_snapshot():
            return dict(manifest=planning_manifest, sources=read_snapshot(engine))
    if os.environ.get("FLOWPILOT_BROWSER_REVENUE_FIXTURE") == "1":
        from revenue_fixture import seed_revenue, read_revenue_snapshot
        from copilot_closure_fixture import seed_closures, read_closure_snapshot
        seed_revenue(engine, DEMO_INSTITUTE_ID)
        seed_closures(engine, DEMO_INSTITUTE_ID)
        @app.get("/_fixture/revenue")
        def revenue_snapshot():
            return read_revenue_snapshot(engine)
        @app.get("/_fixture/closures")
        def closure_snapshot():
            return read_closure_snapshot(engine)
    if options.simulate_payments:
        from payment_simulator import PaymentSimulator
        from app.modules.payments.dispatch import ProviderBinding
        app = create_app(payment_bindings=[ProviderBinding(DEMO_INSTITUTE_ID,
            "browser-simulator", "browser-test-account", PaymentSimulator())])
    try:
        uvicorn.run(app, host="127.0.0.1", port=4198, log_level="warning")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
