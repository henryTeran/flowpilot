from sqlalchemy.orm import Session

from app.modules.services.models import Service
from app.modules.services.repository import save_service
from app.modules.services.schemas import ServiceCreate
from app.shared.ids import new_id


def create_service(db: Session, payload: ServiceCreate) -> Service:
    duration_max = payload.duration_max or payload.duration_min
    service = Service(
        id=new_id("svc"),
        **payload.model_dump(exclude={"duration_max"}),
        duration_max=duration_max,
    )
    return save_service(db, service)
