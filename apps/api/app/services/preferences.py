from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import RecommendationValidationError
from app.core.security import SessionCredential, utc_now
from app.db.models import Game, Genre, Platform, PreferenceType, Tag
from app.db.session import begin_read_committed, begin_repeatable_read
from app.repositories.preferences import PreferenceRepository
from app.schemas.preferences import (
    PreferenceReplaceRequest,
    PreferenceResponse,
    SavedGamePreference,
)
from app.services.anonymous_identity import AnonymousIdentityService


class PreferenceService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.preferences = PreferenceRepository(session)

    def get(self, credential: SessionCredential | None) -> PreferenceResponse:
        begin_repeatable_read(self.session, read_only=True)
        user = AnonymousIdentityService(self.session, self.settings).resolve_active(credential)
        response = self._response(user.id)
        self.session.rollback()
        return response

    def replace(
        self,
        credential: SessionCredential | None,
        payload: PreferenceReplaceRequest,
    ) -> PreferenceResponse:
        begin_read_committed(self.session)
        user = AnonymousIdentityService(self.session, self.settings).resolve_active_for_update(
            credential
        )
        user.updated_at = utc_now()
        game_rows = self._locked_games(payload.selected_game_ids)
        genre_slugs = self._locked_taxonomies(Genre, payload.preferred_genres, "genre")
        tag_slugs = self._locked_taxonomies(Tag, payload.preferred_tags, "tag")
        platform_slugs = self._locked_taxonomies(Platform, payload.preferred_platforms, "platform")
        desired = {
            *((PreferenceType.GAME.value, game.slug) for game in game_rows),
            *((PreferenceType.GENRE.value, slug) for slug in genre_slugs),
            *((PreferenceType.TAG.value, slug) for slug in tag_slugs),
            *((PreferenceType.PLATFORM.value, slug) for slug in platform_slugs),
        }
        changed = self.preferences.replace(user.id, desired)
        if changed:
            self.session.flush()
        response = self._response(user.id)
        if changed:
            self.session.commit()
        else:
            self.session.rollback()
        return response

    def clear(self, credential: SessionCredential | None) -> None:
        begin_read_committed(self.session)
        user = AnonymousIdentityService(self.session, self.settings).resolve_active_for_update(
            credential
        )
        user.updated_at = utc_now()
        changed = self.preferences.clear(user.id)
        self.session.commit() if changed else self.session.rollback()

    def _response(self, user_id: int) -> PreferenceResponse:
        rows = self.preferences.list_for_user(user_id)
        values: dict[str, list[str]] = {kind.value: [] for kind in PreferenceType}
        for row in rows:
            key = (
                row.preference_type.value
                if isinstance(row.preference_type, PreferenceType)
                else str(row.preference_type)
            )
            values[key].append(row.value)
        game_slugs = values[PreferenceType.GAME.value]
        games = list(
            self.session.scalars(select(Game).where(Game.slug.in_(game_slugs)).order_by(Game.slug))
        )
        games_by_slug = {game.slug: game for game in games}
        taxonomy_models = {
            PreferenceType.GENRE.value: Genre,
            PreferenceType.TAG.value: Tag,
            PreferenceType.PLATFORM.value: Platform,
        }
        stale: list[str] = []
        for slug in game_slugs:
            if slug not in games_by_slug:
                stale.append(f"game:{slug}")
        for kind, model in taxonomy_models.items():
            known = set(
                self.session.scalars(select(model.slug).where(model.slug.in_(values[kind])))
            )
            stale.extend(f"{kind}:{slug}" for slug in values[kind] if slug not in known)
        return PreferenceResponse(
            selected_games=[
                SavedGamePreference(id=game.id, slug=game.slug, title=game.title) for game in games
            ],
            preferred_genres=sorted(values[PreferenceType.GENRE.value]),
            preferred_tags=sorted(values[PreferenceType.TAG.value]),
            preferred_platforms=sorted(values[PreferenceType.PLATFORM.value]),
            stale_references=sorted(stale)[:26],
        )

    def _locked_games(self, game_ids: list[int]) -> list[Game]:
        rows = list(
            self.session.scalars(
                select(Game)
                .where(Game.id.in_(game_ids))
                .order_by(Game.slug)
                .with_for_update(read=True)
            )
        )
        missing = sorted(set(game_ids) - {game.id for game in rows})
        if missing:
            raise RecommendationValidationError(
                "One or more selected games do not exist",
                code="unknown_game",
                details={"selected_game_ids": missing},
            )
        return rows

    def _locked_taxonomies(self, model, slugs: list[str], family: str) -> list[str]:  # type: ignore[no-untyped-def]
        rows = list(
            self.session.scalars(
                select(model.slug)
                .where(model.slug.in_(slugs))
                .order_by(model.slug)
                .with_for_update(read=True)
            )
        )
        missing = sorted(set(slugs) - set(rows))
        if missing:
            raise RecommendationValidationError(
                f"One or more selected {family} values do not exist",
                code=f"unknown_{family}",
                details={f"preferred_{family}s": missing},
            )
        return rows
