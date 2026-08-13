from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Game, Interaction, InteractionType

STATE_TYPES = frozenset(
    {
        InteractionType.LIKED,
        InteractionType.DISLIKED,
        InteractionType.PLAYED,
        InteractionType.WISHLISTED,
        InteractionType.RATED,
    }
)


class InteractionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def active_rows(self, user_id: int, *, game_id: int | None = None) -> list[Interaction]:
        statement = select(Interaction).where(
            Interaction.user_id == user_id,
            Interaction.superseded_at.is_(None),
            Interaction.interaction_type.in_(STATE_TYPES),
        )
        if game_id is not None:
            statement = statement.where(Interaction.game_id == game_id)
        return list(
            self.session.scalars(
                statement.order_by(Interaction.occurred_at.desc(), Interaction.id.desc())
            ).all()
        )

    def replace_game_state(
        self,
        *,
        user_id: int,
        game_id: int,
        desired: dict[InteractionType, Decimal | None],
        now: datetime,
    ) -> tuple[bool, list[Interaction]]:
        active = self.active_rows(user_id, game_id=game_id)
        current = {item.interaction_type: item.value for item in active}
        if current == desired:
            return False, active
        next_active = [
            item
            for item in active
            if item.interaction_type in desired and item.value == desired[item.interaction_type]
        ]
        for item in active:
            if item.interaction_type not in desired or item.value != desired[item.interaction_type]:
                item.superseded_at = now
        for interaction_type, value in desired.items():
            if interaction_type not in current or current[interaction_type] != value:
                item = Interaction(
                    user_id=user_id,
                    game_id=game_id,
                    interaction_type=interaction_type,
                    value=value,
                    occurred_at=now,
                )
                self.session.add(item)
                next_active.append(item)
        return True, next_active

    def aggregated_current(self, user_id: int) -> list[tuple[Game, list[Interaction]]]:
        rows = self.session.execute(
            select(Game, Interaction)
            .join(Interaction, Interaction.game_id == Game.id)
            .where(
                Interaction.user_id == user_id,
                Interaction.superseded_at.is_(None),
                Interaction.interaction_type.in_(STATE_TYPES),
            )
            .order_by(Interaction.occurred_at.desc(), Game.id, Interaction.id.desc())
        ).all()
        grouped: dict[int, tuple[Game, list[Interaction]]] = {}
        for game, interaction in rows:
            grouped.setdefault(game.id, (game, []))[1].append(interaction)
        # The query already establishes latest occurrence then game-id ordering;
        # dict insertion order preserves the first row observed for each game.
        return list(grouped.values())
