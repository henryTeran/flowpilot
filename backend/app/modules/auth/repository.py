from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email.lower())).first()


def save_user(db: Session, user: User) -> User:
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
