from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import UserPreference


class PreferenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_user(self, user_id: int) -> list[UserPreference]:
        return list(
            self.session.scalars(
                select(UserPreference)
                .where(UserPreference.user_id == user_id)
                .order_by(UserPreference.preference_type, UserPreference.value)
            ).all()
        )

    def replace(self, user_id: int, desired: set[tuple[str, str]]) -> bool:
        existing = self.list_for_user(user_id)
        current = {(str(item.preference_type), item.value) for item in existing}
        if current == desired:
            return False
        by_key = {(str(item.preference_type), item.value): item for item in existing}
        for key in current - desired:
            self.session.delete(by_key[key])
        for preference_type, value in sorted(desired - current):
            self.session.add(
                UserPreference(
                    user_id=user_id,
                    preference_type=preference_type,
                    value=value,
                    weight=Decimal("1.000"),
                )
            )
        return True

    def clear(self, user_id: int) -> bool:
        result = self.session.execute(
            delete(UserPreference).where(UserPreference.user_id == user_id)
        )
        return bool(result.rowcount)
