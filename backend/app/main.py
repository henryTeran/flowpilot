from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.http import configure_http_middleware
from app.database.base import Base
from app.database.session import engine
from app.modules.appointments.routes import router as appointments_router
from app.modules.auth.routes import router as auth_router
from app.modules.dashboard.routes import router as dashboard_router
from app.modules.dev.routes import router as dev_router
from app.modules.employees.routes import router as employees_router
from app.modules.institutes.routes import router as institutes_router
from app.modules.planning.routes import router as planning_router
from app.modules.realtime.routes import router as realtime_router
from app.modules.services.routes import router as services_router
from app.modules.tickets.routes import router as tickets_router


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.APP_DEBUG,
        version="0.1.0",
        description="MVP backend for FlowPilot Institut Manager.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    configure_http_middleware(app)

    @app.on_event("startup")
    def on_startup() -> None:
        # Mode bootstrap local uniquement. En production, utiliser Alembic.
        if settings.AUTO_CREATE_SCHEMA_ON_STARTUP:
            if settings.is_production_like_env:
                raise RuntimeError(
                    "AUTO_CREATE_SCHEMA_ON_STARTUP est interdit en production. "
                    "Utiliser les migrations Alembic."
                )
            if not settings.is_local_like_env and settings.has_weak_secret_key:
                raise RuntimeError(
                    "Refus du bootstrap SQLAlchemy: SECRET_KEY faible/default hors environnement local/dev/test."
                )
            Base.metadata.create_all(bind=engine)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.APP_NAME}

    prefix = settings.API_V1_PREFIX
    app.include_router(auth_router, prefix=prefix)
    app.include_router(appointments_router, prefix=prefix)
    app.include_router(institutes_router, prefix=prefix)
    app.include_router(employees_router, prefix=prefix)
    app.include_router(services_router, prefix=prefix)
    app.include_router(tickets_router, prefix=prefix)
    app.include_router(planning_router, prefix=prefix)
    app.include_router(dashboard_router, prefix=prefix)
    app.include_router(dev_router, prefix=prefix)
    app.include_router(realtime_router)

    return app


app = create_app()
