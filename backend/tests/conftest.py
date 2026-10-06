import os
import time
from collections.abc import Generator
from tempfile import mkstemp

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.main as main_module
from app.database.base import Base
from app.database.session import get_db
from app.main import app


def _remove_fixture_database(path: str) -> None:
    # Windows can briefly retain a sharing lock after the engine is disposed.
    # Retry only that specific condition, and still fail persistent cleanup.
    for attempt in range(10):
        try:
            os.remove(path)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) != 32 or attempt == 9:
                raise
            time.sleep(0.1)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    fd, db_path = mkstemp(prefix="flowpilot-tests-", suffix=".db")
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    original_engine = main_module.engine
    main_module.engine = engine
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        main_module.engine = original_engine
        engine.dispose()
        if os.path.exists(db_path):
            _remove_fixture_database(db_path)
