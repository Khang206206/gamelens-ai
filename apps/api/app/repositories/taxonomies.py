from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Genre, Platform, Tag


class TaxonomyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_genres(self) -> list[Genre]:
        return list(self.session.scalars(select(Genre).order_by(func.lower(Genre.name), Genre.id)))

    def list_tags(self) -> list[Tag]:
        return list(self.session.scalars(select(Tag).order_by(func.lower(Tag.name), Tag.id)))

    def list_platforms(self) -> list[Platform]:
        return list(
            self.session.scalars(select(Platform).order_by(func.lower(Platform.name), Platform.id))
        )
