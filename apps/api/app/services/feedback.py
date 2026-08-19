from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ResourceNotFoundError
from app.core.security import SessionCredential, utc_now
from app.db.models import Game, Interaction, InteractionType
from app.db.session import begin_read_committed, begin_repeatable_read
from app.repositories.interactions import InteractionRepository
from app.schemas.feedback import FeedbackPage, FeedbackReplaceRequest, FeedbackResource
from app.services.anonymous_identity import AnonymousIdentityService


class FeedbackService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.session = session
        self.settings = settings
        self.clock = clock
        self.interactions = InteractionRepository(session)

    def list(
        self,
        credential: SessionCredential | None,
        *,
        page: int,
        page_size: int,
    ) -> FeedbackPage:
        begin_repeatable_read(self.session, read_only=True)
        user = AnonymousIdentityService(self.session, self.settings).resolve_active(credential)
        groups = self.interactions.aggregated_current(user.id)
        total = len(groups)
        start = (page - 1) * page_size
        response = FeedbackPage(
            items=[self._resource(game, rows) for game, rows in groups[start : start + page_size]],
            page=page,
            page_size=page_size,
            total=total,
        )
        self.session.rollback()
        return response

    def replace(
        self,
        credential: SessionCredential | None,
        *,
        game_id: int,
        payload: FeedbackReplaceRequest,
    ) -> FeedbackResource | None:
        begin_read_committed(self.session)
        user = AnonymousIdentityService(self.session, self.settings).resolve_active_for_update(
            credential
        )
        game = self.session.scalar(
            select(Game).where(Game.id == game_id).with_for_update(read=True)
        )
        if game is None:
            raise ResourceNotFoundError("The requested game does not exist", code="game_not_found")
        now = self.clock()
        user.updated_at = now
        desired: dict[InteractionType, Decimal | None] = {}
        if payload.reaction is not None:
            desired[InteractionType(payload.reaction)] = None
        if payload.played:
            desired[InteractionType.PLAYED] = None
        if payload.wishlisted:
            desired[InteractionType.WISHLISTED] = None
        if payload.rating is not None:
            desired[InteractionType.RATED] = payload.rating
        changed, active = self.interactions.replace_game_state(
            user_id=user.id,
            game_id=game.id,
            desired=desired,
            now=now,
        )
        response = None if not active else self._resource(game, active)
        if changed:
            self.session.commit()
        else:
            self.session.rollback()
        return response

    def clear(self, credential: SessionCredential | None, *, game_id: int) -> None:
        empty = FeedbackReplaceRequest(
            reaction=None,
            played=False,
            wishlisted=False,
            rating=None,
        )
        self.replace(credential, game_id=game_id, payload=empty)

    @staticmethod
    def _resource(game: Game, rows: list[Interaction]) -> FeedbackResource:
        by_type = {row.interaction_type: row for row in rows}
        reaction = next(
            (
                row.interaction_type.value
                for row in rows
                if row.interaction_type in {InteractionType.LIKED, InteractionType.DISLIKED}
            ),
            None,
        )
        return FeedbackResource(
            game_id=game.id,
            game_slug=game.slug,
            game_title=game.title,
            reaction=reaction,
            played=InteractionType.PLAYED in by_type,
            wishlisted=InteractionType.WISHLISTED in by_type,
            rating=(
                float(by_type[InteractionType.RATED].value)
                if InteractionType.RATED in by_type
                else None
            ),
            latest_occurred_at=max(row.occurred_at for row in rows),
        )
