from app.db.models.catalog import (
    Game,
    Genre,
    Platform,
    Tag,
    game_genres,
    game_platforms,
    game_tags,
)
from app.db.models.collaborative import (
    CollaborativeContributionConsent,
    CollaborativeDataRevision,
)
from app.db.models.users import (
    Interaction,
    InteractionType,
    PreferenceType,
    RecommendationEvent,
    User,
    UserPreference,
)

__all__ = [
    "CollaborativeContributionConsent",
    "CollaborativeDataRevision",
    "Game",
    "Genre",
    "Interaction",
    "InteractionType",
    "Platform",
    "PreferenceType",
    "RecommendationEvent",
    "Tag",
    "User",
    "UserPreference",
    "game_genres",
    "game_platforms",
    "game_tags",
]
