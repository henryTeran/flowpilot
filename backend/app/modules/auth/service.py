from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.modules.auth.repository import get_user_by_email
from app.modules.auth.schemas import LoginResponse


def login(db: Session, email: str, password: str) -> LoginResponse:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte inactif")

    token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role, "institute_id": user.institute_id},
    )
    return LoginResponse(access_token=token, role=user.role, institute_id=user.institute_id)
