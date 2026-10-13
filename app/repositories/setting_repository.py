from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.setting import Setting


class SettingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str) -> str | None:
        return self.db.scalar(select(Setting.value).where(Setting.key == key))

    def set(self, key: str, value: str) -> None:
        row = self.db.scalar(select(Setting).where(Setting.key == key))
        if row is None:
            self.db.add(Setting(key=key, value=value))
        else:
            row.value = value
        self.db.flush()
