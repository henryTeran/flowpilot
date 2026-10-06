"""Owned loopback browser-test backend; never uses an existing database."""
import os
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

with TemporaryDirectory(prefix="flowpilot-browser-") as directory:
    database = Path(directory).resolve() / "browser.sqlite"
    os.environ.update(
        DATABASE_URL="sqlite:///" + database.as_posix(), APP_ENV="test",
        SECRET_KEY=secrets.token_urlsafe(48), APP_DEBUG="false",
        AUTO_CREATE_SCHEMA_ON_STARTUP="false", CORS_ORIGINS="http://127.0.0.1:4199",
    )
    from app.main import app
    from app.database.base import Base
    from app.database.session import engine
    from app.core.security import hash_password
    from app.modules.auth.models import User
    from app.modules.dev.routes import init_demo_data, DEMO_INSTITUTE_ID
    from sqlalchemy.orm import Session
    import uvicorn

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        init_demo_data(db)
        for role, name in (("responsable_institut", "manager"), ("accueil", "cashier")):
            db.add(User(id="browser-" + name, email=name + "@browser.example.com",
                        password_hash=hash_password("Browser-test-only-2026"),
                        role=role, institute_id=DEMO_INSTITUTE_ID, status="active"))
        db.commit()
    try:
        uvicorn.run(app, host="127.0.0.1", port=4198, log_level="warning")
    finally:
        engine.dispose()
