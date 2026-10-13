from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_session import UserSession


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def admin_exists(self) -> bool:
        return self.db.scalar(select(func.count()).select_from(User).where(User.is_admin.is_(True))) > 0

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    # --- Sessions ---
    def add_session(self, session: UserSession) -> UserSession:
        self.db.add(session)
        self.db.flush()
        return session

    def get_session_by_hash(self, token_hash: str) -> UserSession | None:
        return self.db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))

    def delete_session(self, session: UserSession) -> None:
        self.db.delete(session)

    def delete_expired_sessions(self, now: datetime) -> None:
        self.db.execute(delete(UserSession).where(UserSession.expires_at <= now))
