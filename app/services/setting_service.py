from sqlalchemy.orm import Session

from app.repositories.setting_repository import SettingRepository
from app.schemas.setting import SiteSettingsOut, SiteSettingsUpdate
from app.services.base import commit_or_conflict

KEY_MAINTENANCE_MODE = "maintenance_mode"
KEY_MAINTENANCE_MESSAGE = "maintenance_message"
DEFAULT_MAINTENANCE_MESSAGE = "Die Website befindet sich derzeit im Wartungsmodus. Bitte versuchen Sie es später erneut."


class SettingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SettingRepository(db)

    def is_maintenance(self) -> bool:
        return (self.repo.get(KEY_MAINTENANCE_MODE) or "false").strip().lower() == "true"

    def maintenance_message(self) -> str:
        return self.repo.get(KEY_MAINTENANCE_MESSAGE) or DEFAULT_MAINTENANCE_MESSAGE

    def get(self) -> SiteSettingsOut:
        return SiteSettingsOut(maintenance_mode=self.is_maintenance(), maintenance_message=self.maintenance_message())

    def update(self, data: SiteSettingsUpdate) -> SiteSettingsOut:
        if data.maintenance_mode is not None:
            self.repo.set(KEY_MAINTENANCE_MODE, "true" if data.maintenance_mode else "false")
        if data.maintenance_message is not None:
            self.repo.set(KEY_MAINTENANCE_MESSAGE, data.maintenance_message.strip() or DEFAULT_MAINTENANCE_MESSAGE)
        commit_or_conflict(self.db)
        return self.get()
