from enum import StrEnum

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    DIRECTION = "direction"
    RESPONSABLE_INSTITUT = "responsable_institut"
    ACCUEIL = "accueil"
    COLLABORATRICE = "collaboratrice"


TERRAIN_ROLES = {
    UserRole.RESPONSABLE_INSTITUT,
    UserRole.ACCUEIL,
    UserRole.COLLABORATRICE,
}


def can_manage_ticket(role: UserRole | str) -> bool:
    try:
        normalized = UserRole(str(role))
    except ValueError:
        return False
    return normalized in {UserRole.RESPONSABLE_INSTITUT, UserRole.ACCUEIL}


def can_view_direction_dashboard(role: UserRole | str) -> bool:
    try:
        normalized = UserRole(str(role))
    except ValueError:
        return False
    return normalized in {UserRole.SUPER_ADMIN, UserRole.DIRECTION}


def _decode_current_user(request: Request) -> dict[str, str | None]:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token manquant")

    token = authorization.replace("Bearer ", "", 1).strip()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token invalide") from exc

    role = payload.get("role")
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rôle manquant")

    return {
        "role": str(role),
        "institute_id": payload.get("institute_id"),
        "sub": payload.get("sub"),
    }


def require_ticket_manager(request: Request) -> dict[str, str | None]:
    current_user = _decode_current_user(request)
    if not can_manage_ticket(current_user["role"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission insuffisante")
    return current_user


def require_same_institute(current_user: dict[str, str | None], institute_id: str | None) -> dict[str, str | None]:
    if institute_id and current_user.get("institute_id") and current_user["institute_id"] != institute_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Institut non autorisé")
    return current_user
