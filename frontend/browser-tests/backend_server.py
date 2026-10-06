"""Owned loopback browser-test backend; never uses an existing database."""
import os
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

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        init_demo_data(db)
        # Explicit fixture capacity: two qualified staff share one treatment room.
        db.add(Resource(id="browser-room", institute_id=DEMO_INSTITUTE_ID,
                        name="Browser shared room", kind="room", capabilities=[], status="active"))
        db.add(ResourceRequirement(id="browser-room-need", institute_id=DEMO_INSTITUTE_ID,
                                   service_id="svc-soin-profond", kind="room", capability="", quantity=1))
        for role, name in (("responsable_institut", "manager"), ("accueil", "cashier")):
            db.add(User(id="browser-" + name, email=name + "@browser.example.com",
                        password_hash=hash_password("Browser-test-only-2026"),
                        role=role, institute_id=DEMO_INSTITUTE_ID, status="active"))
        db.commit()
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
