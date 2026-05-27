from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.auth.schemas import LoginRequest, LoginResponse
from app.modules.auth.service import login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def post_login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    return login(db, payload.email, payload.password)
