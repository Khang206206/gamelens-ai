from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from gamelens_recommender.interaction_snapshot import (
    MAX_POSITIVE_EDGES,
    MAX_PROFILES,
    canonicalize_profiles,
)
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import Select, Subquery

from app.db.models import (
    CollaborativeContributionConsent,
    CollaborativeDataRevision,
    Game,
    Interaction,
    InteractionType,
    PreferenceType,
    User,
    UserPreference,
)
from app.db.session import begin_repeatable_read
from app.repositories.recommendation_catalog import RecommendationCatalogRepository

RATING_POSITIVE_THRESHOLD = Decimal("7")
MAX_SOURCE_ROWS = MAX_POSITIVE_EDGES * 2
STREAM_BATCH_SIZE = 1_000
_CUTOFF_SESSION_KEY = "collaborative_snapshot_cutoff"


class CollaborativeSnapshotError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExtractedInteractionSnapshot:
    cutoff: datetime
    data_revision: int
    catalog_fingerprint: str
    profiles: tuple[tuple[str, ...], ...]
    profile_user_ids: tuple[int, ...]
    profile_authority_valid_until: tuple[datetime, ...]
    exclusion_counts: dict[str, int]
    eligible_contributors: int


@dataclass
class _GameSignals:
    liked: bool = False
    disliked: bool = False
    latest_rating: tuple[datetime, int, Decimal] | None = None
    other_types: set[InteractionType] = field(default_factory=set)


@dataclass(frozen=True)
class _PinnedSnapshot:
    cutoff: datetime
    transaction: object


def _eligible_users_subquery(
    *,
    cutoff: datetime,
    personalization_consent_version: str,
    contribution_consent_version: str,
) -> Subquery:
    return (
        select(
            User.id.label("user_id"),
            User.expires_at.label("expires_at"),
            User.revoked_at.label("revoked_at"),
            CollaborativeContributionConsent.withdrawn_at.label("contribution_withdrawn_at"),
        )
        .join(
            CollaborativeContributionConsent,
            CollaborativeContributionConsent.user_id == User.id,
        )
        .where(
            User.consent_version == personalization_consent_version,
            User.consented_at.is_not(None),
            User.consented_at <= cutoff,
            User.expires_at.is_not(None),
            User.expires_at > cutoff,
            or_(User.revoked_at.is_(None), User.revoked_at > cutoff),
            CollaborativeContributionConsent.consent_version == contribution_consent_version,
            CollaborativeContributionConsent.granted_at <= cutoff,
            or_(
                CollaborativeContributionConsent.withdrawn_at.is_(None),
                CollaborativeContributionConsent.withdrawn_at > cutoff,
            ),
        )
        .subquery("eligible_collaborative_users")
    )


def _saved_game_preferences_query(
    eligible_users: Subquery,
) -> Select[tuple[int, str]]:
    return (
        select(UserPreference.user_id, UserPreference.value)
        .select_from(UserPreference)
        .join(
            eligible_users,
            eligible_users.c.user_id == UserPreference.user_id,
        )
        .where(
            UserPreference.preference_type == PreferenceType.GAME,
            UserPreference.weight > 0,
        )
    )


def _interaction_rows_query(
    eligible_users: Subquery,
) -> Select[
    tuple[
        int,
        str,
        InteractionType,
        Decimal | None,
        datetime,
        datetime | None,
        int,
    ]
]:
    return (
        select(
            Interaction.user_id,
            Game.slug,
            Interaction.interaction_type,
            Interaction.value,
            Interaction.occurred_at,
            Interaction.superseded_at,
            Interaction.id,
        )
        .select_from(Interaction)
        .join(eligible_users, eligible_users.c.user_id == Interaction.user_id)
        .join(Game, Game.id == Interaction.game_id)
    )


def begin_collaborative_snapshot(session: Session) -> datetime:
    """Start and pin the read-only MVCC snapshot before returning to the caller."""

    if session.get_bind().dialect.name != "postgresql":
        raise CollaborativeSnapshotError(
            "unsupported_database",
            "Live collaborative extraction requires PostgreSQL",
        )
    session.info.pop(_CUTOFF_SESSION_KEY, None)
    begin_repeatable_read(session, read_only=True)
    transaction = (
        session.execute(
            text(
                """
                SELECT clock_timestamp() AS cutoff,
                       pg_current_snapshot()::text AS snapshot_token,
                       current_setting('transaction_isolation') AS isolation_level,
                       current_setting('transaction_read_only') AS read_only
                """
            )
        )
        .mappings()
        .one()
    )
    if transaction["isolation_level"] != "repeatable read" or transaction["read_only"] != "on":
        raise CollaborativeSnapshotError(
            "extractor_transaction_invalid",
            "Live extraction requires one REPEATABLE READ, READ ONLY transaction",
        )
    cutoff = transaction["cutoff"]
    session.info[_CUTOFF_SESSION_KEY] = _PinnedSnapshot(
        cutoff=cutoff, transaction=session.get_transaction()
    )
    return cutoff


class CollaborativeSnapshotRepository:
    """Extract an aggregate-ready snapshot without persisting row-level user data."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def extract(
        self,
        *,
        personalization_consent_version: str,
        contribution_consent_version: str,
    ) -> ExtractedInteractionSnapshot:
        cutoff = self._verified_cutoff()
        data_revision = self.session.scalar(
            select(CollaborativeDataRevision.revision).where(
                CollaborativeDataRevision.singleton_id == 1
            )
        )
        if data_revision is None:
            raise CollaborativeSnapshotError(
                "revision_unavailable",
                "Collaborative source revision singleton is unavailable",
            )

        catalog = RecommendationCatalogRepository(self.session).load()
        if catalog.model_snapshot is None:
            reason = catalog.model_unavailable_reason
            raise CollaborativeSnapshotError(
                "catalog_mismatch",
                f"Collaborative extraction requires a valid catalog: {reason}",
            )
        catalog_slugs = frozenset(catalog.games_by_slug)

        eligible_users = _eligible_users_subquery(
            cutoff=cutoff,
            personalization_consent_version=personalization_consent_version,
            contribution_consent_version=contribution_consent_version,
        )
        eligible_user_rows = list(
            self.session.execute(
                select(
                    eligible_users.c.user_id,
                    eligible_users.c.expires_at,
                    eligible_users.c.revoked_at,
                    eligible_users.c.contribution_withdrawn_at,
                )
                .order_by(eligible_users.c.user_id)
                .limit(MAX_PROFILES + 1)
            ).all()
        )
        if len(eligible_user_rows) > MAX_PROFILES:
            raise CollaborativeSnapshotError(
                "snapshot_limit_exceeded",
                "Eligible contributor limit exceeded",
            )
        eligible_user_ids = [int(row.user_id) for row in eligible_user_rows]
        authority_valid_until_by_user: dict[int, datetime] = {}
        for row in eligible_user_rows:
            horizons = tuple(
                value
                for value in (
                    row.expires_at,
                    row.revoked_at,
                    row.contribution_withdrawn_at,
                )
                if value is not None
            )
            if not horizons:
                raise CollaborativeSnapshotError(
                    "authority_invalid",
                    "Eligible contributor has no bounded authority horizon",
                )
            authority_valid_until_by_user[int(row.user_id)] = min(horizons)

        exclusions = self._eligibility_exclusions(
            cutoff=cutoff,
            personalization_consent_version=personalization_consent_version,
            contribution_consent_version=contribution_consent_version,
        )
        profiles_by_user = {user_id: set() for user_id in eligible_user_ids}
        saved_games: defaultdict[int, set[str]] = defaultdict(set)
        if eligible_user_ids:
            preferences = self.session.execute(
                _saved_game_preferences_query(eligible_users)
                .where(
                    UserPreference.created_at <= cutoff,
                    UserPreference.updated_at <= cutoff,
                )
                .order_by(UserPreference.user_id, UserPreference.value)
                .limit(MAX_POSITIVE_EDGES + 1)
                .execution_options(yield_per=STREAM_BATCH_SIZE)
            )
            for preference_count, (user_id, game_slug) in enumerate(preferences, start=1):
                if preference_count > MAX_POSITIVE_EDGES:
                    raise CollaborativeSnapshotError(
                        "snapshot_limit_exceeded",
                        "Saved-game preference limit exceeded",
                    )
                if game_slug in catalog_slugs:
                    saved_games[user_id].add(game_slug)
                else:
                    exclusions["unknown_game"] += 1

        signals: defaultdict[tuple[int, str], _GameSignals] = defaultdict(_GameSignals)
        if eligible_user_ids:
            interaction_rows = self.session.execute(
                _interaction_rows_query(eligible_users)
                .order_by(
                    Interaction.user_id,
                    Game.slug,
                    Interaction.occurred_at,
                    Interaction.id,
                )
                .limit(MAX_SOURCE_ROWS + 1)
                .execution_options(yield_per=STREAM_BATCH_SIZE)
            )
            for interaction_count, row in enumerate(interaction_rows, start=1):
                if interaction_count > MAX_SOURCE_ROWS:
                    raise CollaborativeSnapshotError(
                        "snapshot_limit_exceeded",
                        "Interaction source-row limit exceeded",
                    )
                if row.occurred_at > cutoff:
                    exclusions["post_cutoff"] += 1
                    continue
                if row.superseded_at is not None and row.superseded_at <= cutoff:
                    exclusions["superseded"] += 1
                    continue
                signal = signals[(row.user_id, row.slug)]
                interaction_type = row.interaction_type
                if interaction_type == InteractionType.LIKED:
                    signal.liked = True
                elif interaction_type == InteractionType.DISLIKED:
                    signal.disliked = True
                elif interaction_type == InteractionType.RATED:
                    assert row.value is not None
                    signal.latest_rating = (row.occurred_at, row.id, row.value)
                else:
                    signal.other_types.add(interaction_type)

        all_signal_keys = set(signals)
        all_signal_keys.update(
            (user_id, game_slug)
            for user_id, game_slugs in saved_games.items()
            for game_slug in game_slugs
        )
        for user_id, game_slug in sorted(all_signal_keys):
            signal = signals[(user_id, game_slug)]
            saved = game_slug in saved_games[user_id]
            if signal.disliked:
                exclusions["disliked"] += 1
            elif (
                signal.liked
                or signal.latest_rating is not None
                and signal.latest_rating[2] >= (RATING_POSITIVE_THRESHOLD)
                or saved
            ):
                profiles_by_user[user_id].add(game_slug)
            elif signal.latest_rating is not None:
                exclusions["low_rating"] += 1
            elif InteractionType.WISHLISTED in signal.other_types:
                exclusions["wishlisted_only"] += 1
            elif InteractionType.PLAYED in signal.other_types:
                exclusions["played_only"] += 1
            elif InteractionType.VIEWED in signal.other_types:
                exclusions["viewed_only"] += 1

        identified_profiles = tuple(
            sorted(
                (
                    tuple(sorted(profiles_by_user[user_id])),
                    user_id,
                    authority_valid_until_by_user[user_id],
                )
                for user_id in eligible_user_ids
            )
        )
        profiles = canonicalize_profiles(
            (profile for profile, _user_id, _horizon in identified_profiles),
            catalog_slugs=catalog_slugs,
        )
        if profiles != tuple(profile for profile, _user_id, _horizon in identified_profiles):
            raise CollaborativeSnapshotError(
                "snapshot_invalid",
                "Contributor profile mapping is not canonical",
            )
        return ExtractedInteractionSnapshot(
            cutoff=cutoff,
            data_revision=int(data_revision),
            catalog_fingerprint=catalog.model_snapshot.fingerprint,
            profiles=profiles,
            profile_user_ids=tuple(user_id for _profile, user_id, _horizon in identified_profiles),
            profile_authority_valid_until=tuple(
                horizon for _profile, _user_id, horizon in identified_profiles
            ),
            exclusion_counts=dict(sorted(exclusions.items())),
            eligible_contributors=len(eligible_user_ids),
        )

    def _verified_cutoff(self) -> datetime:
        pinned = self.session.info.get(_CUTOFF_SESSION_KEY)
        if (
            not isinstance(pinned, _PinnedSnapshot)
            or pinned.transaction is None
            or pinned.transaction is not self.session.get_transaction()
        ):
            raise CollaborativeSnapshotError(
                "extractor_transaction_invalid",
                "Collaborative extraction requires a pinned snapshot transaction",
            )
        transaction = (
            self.session.execute(
                text(
                    """
                SELECT current_setting('transaction_isolation') AS isolation_level,
                       current_setting('transaction_read_only') AS read_only
                """
                )
            )
            .mappings()
            .one()
        )
        if transaction["isolation_level"] != "repeatable read" or transaction["read_only"] != "on":
            raise CollaborativeSnapshotError(
                "extractor_transaction_invalid",
                "Live extraction requires one REPEATABLE READ, READ ONLY transaction",
            )
        return pinned.cutoff

    def _eligibility_exclusions(
        self,
        *,
        cutoff: datetime,
        personalization_consent_version: str,
        contribution_consent_version: str,
    ) -> Counter[str]:
        exclusions: Counter[str] = Counter()
        exclusions["base_consent_mismatch"] = self._count_users(
            or_(
                User.consent_version.is_(None),
                User.consent_version != personalization_consent_version,
                User.consented_at.is_(None),
                User.consented_at > cutoff,
            )
        )
        exclusions["expired"] = self._count_users(
            or_(User.expires_at.is_(None), User.expires_at <= cutoff)
        )
        exclusions["revoked"] = self._count_users(
            User.revoked_at.is_not(None), User.revoked_at <= cutoff
        )
        contribution_count = self.session.scalar(
            select(func.count(User.id))
            .select_from(User)
            .outerjoin(
                CollaborativeContributionConsent,
                CollaborativeContributionConsent.user_id == User.id,
            )
            .where(
                or_(
                    CollaborativeContributionConsent.user_id.is_(None),
                    CollaborativeContributionConsent.consent_version
                    != contribution_consent_version,
                    CollaborativeContributionConsent.granted_at > cutoff,
                    CollaborativeContributionConsent.withdrawn_at <= cutoff,
                )
            )
        )
        exclusions["noncontributing"] = int(contribution_count or 0)
        return exclusions

    def _count_users(self, *conditions: object) -> int:
        count = self.session.scalar(
            select(func.count(User.id)).select_from(User).where(*conditions)
        )
        return int(count or 0)


def verify_data_revision(session: Session, *, expected_revision: int) -> None:
    verified_data_revision_time(session, expected_revision=expected_revision)


def verified_data_revision_time(session: Session, *, expected_revision: int) -> datetime:
    record = session.execute(
        select(
            CollaborativeDataRevision.revision,
            func.clock_timestamp().label("database_time"),
        ).where(CollaborativeDataRevision.singleton_id == 1)
    ).one_or_none()
    if record is None:
        raise CollaborativeSnapshotError(
            "revision_unavailable",
            "Collaborative source revision singleton is unavailable",
        )
    if record.revision != expected_revision:
        raise CollaborativeSnapshotError(
            "revision_race",
            "Collaborative source revision changed after extraction",
        )
    return record.database_time
