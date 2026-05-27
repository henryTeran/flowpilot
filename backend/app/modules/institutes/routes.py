from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.institutes.repository import list_institutes
from app.modules.institutes.schemas import InstituteRead

router = APIRouter(prefix="/institutes", tags=["institutes"])


@router.get("", response_model=list[InstituteRead])
def get_accessible_institutes(db: Session = Depends(get_db)) -> list[InstituteRead]:
    # MVP : pas encore filtré par token. Le filtrage rôle/institut viendra avec l'auth complète.
    return list_institutes(db)
