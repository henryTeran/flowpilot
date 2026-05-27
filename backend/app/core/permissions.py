from enum import StrEnum


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


def can_manage_ticket(role: UserRole) -> bool:
    return role in {UserRole.RESPONSABLE_INSTITUT, UserRole.ACCUEIL}


def can_view_direction_dashboard(role: UserRole) -> bool:
    return role in {UserRole.SUPER_ADMIN, UserRole.DIRECTION}
