from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeArtifactContributor,
    CollaborativeContributionConsent,
    Game,
    Interaction,
    InteractionType,
    PreferenceType,
    User,
    UserPreference,
)
from app.db.seed import load_seed_file, seed_database
from app.repositories.interactions import InteractionRepository
from app.repositories.preferences import PreferenceRepository
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import make_consented_user

pytestmark = pytest.mark.integration

BUILD_ID = "stage5-live-labels-v1"
CONTRIBUTION_VERSION = "stage-5-contribution-v1"
CATALOG_FINGERPRINT = "a" * 64
INTERACTION_FINGERPRINT = "b" * 64


def _register_build(
    session: Session,
    *,
    initial_label: str,
) -> tuple[User, Game, list[Game], CollaborativeArtifactBuild, datetime, object]:
    seed_database(session, load_seed_file())
    games = list(session.scalars(select(Game).order_by(Game.id).limit(2)).all())
    assert len(games) == 2
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=1)
    source_time = cutoff - timedelta(minutes=10)
    user = make_consented_user(
        f"label-contributor-{initial_label}",
        consented_at=now - timedelta(days=60),
        expires_at=now + timedelta(days=60),
    )
    session.add(user)
    session.flush()
    session.add(
        CollaborativeContributionConsent(
            user_id=user.id,
            consent_version=CONTRIBUTION_VERSION,
            granted_at=now - timedelta(days=30),
        )
    )

    label: object
    if initial_label == "liked":
        label = Interaction(
            user_id=user.id,
            game_id=games[0].id,
            interaction_type=InteractionType.LIKED,
            occurred_at=source_time,
        )
    elif initial_label == "rating":
        label = Interaction(
            user_id=user.id,
            game_id=games[0].id,
            interaction_type=InteractionType.RATED,
            value=Decimal("8.00"),
            occurred_at=source_time,
        )
    elif initial_label == "preference":
        label = UserPreference(
            user_id=user.id,
            preference_type=PreferenceType.GAME,
            value=games[0].slug,
            weight=Decimal("1.000"),
            created_at=source_time,
            updated_at=source_time,
        )
    else:
        raise AssertionError(f"Unsupported initial label: {initial_label}")
    session.add(label)

    build = CollaborativeArtifactBuild(
        build_id=BUILD_ID,
        source_kind="live",
        status="active",
        registered_revision=7,
        invalidation_epoch=0,
        expected_contributor_count=1,
        current_contributor_count=0,
        consent_version=CONTRIBUTION_VERSION,
        catalog_fingerprint=CATALOG_FINGERPRINT,
        interaction_fingerprint=INTERACTION_FINGERPRINT,
        cutoff=cutoff,
        valid_until=now + timedelta(days=30),
    )
    session.add(build)
    session.flush()
    session.add(CollaborativeArtifactContributor(build_id=build.build_id, user_id=user.id))
    session.commit()
    session.expire_all()
    registered = session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert registered is not None
    assert registered.status == "active"
    return user, games[0], games, registered, now, label


def _assert_active(session: Session) -> None:
    session.expire_all()
    build = session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    assert build.status == "active"
    assert build.invalidation_epoch == 0
    assert build.invalidated_at is None


def _assert_invalidated(session: Session) -> None:
    session.expire_all()
    build = session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    assert build.status == "invalidated"
    assert build.invalidation_epoch == 1
    assert build.invalidated_at is not None


@pytest.mark.parametrize(
    ("initial_label", "mutation"),
    [
        ("liked", "dislike"),
        ("liked", "clear_feedback"),
        ("rating", "low_rating"),
        ("preference", "delete_preference"),
        ("preference", "clear_preferences"),
        ("preference", "dislike_override"),
    ],
)
def test_removing_or_overriding_an_included_positive_invalidates_on_commit(
    postgres_session: Session,
    initial_label: str,
    mutation: str,
) -> None:
    user, game, _games, _build, now, label = _register_build(
        postgres_session,
        initial_label=initial_label,
    )

    if mutation == "dislike":
        InteractionRepository(postgres_session).replace_game_state(
            user_id=user.id,
            game_id=game.id,
            desired={InteractionType.DISLIKED: None},
            now=now,
        )
    elif mutation == "clear_feedback":
        InteractionRepository(postgres_session).replace_game_state(
            user_id=user.id,
            game_id=game.id,
            desired={},
            now=now,
        )
    elif mutation == "low_rating":
        InteractionRepository(postgres_session).replace_game_state(
            user_id=user.id,
            game_id=game.id,
            desired={InteractionType.RATED: Decimal("6.00")},
            now=now,
        )
    elif mutation == "delete_preference":
        persisted = postgres_session.get(UserPreference, label.id)  # type: ignore[attr-defined]
        assert persisted is not None
        postgres_session.delete(persisted)
    elif mutation == "clear_preferences":
        assert PreferenceRepository(postgres_session).clear(user.id)
    elif mutation == "dislike_override":
        postgres_session.add(
            Interaction(
                user_id=user.id,
                game_id=game.id,
                interaction_type=InteractionType.DISLIKED,
                occurred_at=now,
            )
        )
    else:
        raise AssertionError(f"Unsupported mutation: {mutation}")

    postgres_session.commit()
    _assert_invalidated(postgres_session)


def test_positive_to_positive_replacement_keeps_the_build_active(
    postgres_session: Session,
) -> None:
    user, game, _games, _build, now, _label = _register_build(
        postgres_session,
        initial_label="rating",
    )

    changed, _active = InteractionRepository(postgres_session).replace_game_state(
        user_id=user.id,
        game_id=game.id,
        desired={InteractionType.RATED: Decimal("9.00")},
        now=now,
    )
    assert changed
    postgres_session.commit()

    _assert_active(postgres_session)


@pytest.mark.parametrize(
    ("interaction_type", "value"),
    [
        (InteractionType.LIKED, None),
        (InteractionType.RATED, Decimal("6.00")),
        (InteractionType.VIEWED, None),
        (InteractionType.PLAYED, None),
        (InteractionType.WISHLISTED, None),
    ],
)
def test_post_cutoff_positive_and_non_labels_do_not_invalidate(
    postgres_session: Session,
    interaction_type: InteractionType,
    value: Decimal | None,
) -> None:
    user, _game, games, _build, now, _label = _register_build(
        postgres_session,
        initial_label="preference",
    )
    postgres_session.add(
        Interaction(
            user_id=user.id,
            game_id=games[1].id,
            interaction_type=interaction_type,
            value=value,
            occurred_at=now,
        )
    )
    postgres_session.commit()

    _assert_active(postgres_session)


@pytest.mark.parametrize("label_kind", ["interaction", "preference"])
def test_removing_a_label_created_after_cutoff_does_not_invalidate(
    postgres_session: Session,
    label_kind: str,
) -> None:
    user, _game, games, _build, now, _label = _register_build(
        postgres_session,
        initial_label="preference",
    )
    if label_kind == "interaction":
        post_cutoff_label: Interaction | UserPreference = Interaction(
            user_id=user.id,
            game_id=games[1].id,
            interaction_type=InteractionType.LIKED,
            occurred_at=now,
        )
    else:
        post_cutoff_label = UserPreference(
            user_id=user.id,
            preference_type=PreferenceType.GAME,
            value=games[1].slug,
            weight=Decimal("1.000"),
            created_at=now,
            updated_at=now,
        )
    postgres_session.add(post_cutoff_label)
    postgres_session.commit()
    _assert_active(postgres_session)

    postgres_session.delete(post_cutoff_label)
    postgres_session.commit()

    _assert_active(postgres_session)


def test_label_invalidation_rolls_back_with_the_failed_transaction(
    postgres_session: Session,
) -> None:
    user, game, _games, build, now, _label = _register_build(
        postgres_session,
        initial_label="liked",
    )
    InteractionRepository(postgres_session).replace_game_state(
        user_id=user.id,
        game_id=game.id,
        desired={},
        now=now,
    )
    postgres_session.flush()
    postgres_session.execute(
        text("SET CONSTRAINTS trg_interactions_collaborative_label_invalidation IMMEDIATE")
    )
    postgres_session.refresh(build)
    assert build.status == "invalidated"

    postgres_session.rollback()
    _assert_active(postgres_session)

    active_like = postgres_session.scalar(
        select(Interaction).where(
            Interaction.user_id == user.id,
            Interaction.game_id == game.id,
            Interaction.interaction_type == InteractionType.LIKED,
            Interaction.superseded_at.is_(None),
        )
    )
    assert active_like is not None


def test_contributor_registration_requires_a_source_cutoff(
    postgres_session: Session,
) -> None:
    seed_database(postgres_session, load_seed_file())
    now = datetime.now(UTC)
    user = make_consented_user(
        "missing-cutoff-contributor",
        consented_at=now - timedelta(days=60),
        expires_at=now + timedelta(days=60),
    )
    postgres_session.add(user)
    postgres_session.flush()
    postgres_session.add_all(
        [
            CollaborativeContributionConsent(
                user_id=user.id,
                consent_version=CONTRIBUTION_VERSION,
                granted_at=now - timedelta(days=30),
            ),
            CollaborativeArtifactBuild(
                build_id=BUILD_ID,
                source_kind="live",
                status="active",
                registered_revision=7,
                invalidation_epoch=0,
                expected_contributor_count=1,
                current_contributor_count=0,
                consent_version=CONTRIBUTION_VERSION,
                catalog_fingerprint=CATALOG_FINGERPRINT,
                interaction_fingerprint=INTERACTION_FINGERPRINT,
                cutoff=None,
                valid_until=now + timedelta(days=30),
            ),
        ]
    )
    postgres_session.flush()
    postgres_session.add(CollaborativeArtifactContributor(build_id=BUILD_ID, user_id=user.id))

    with pytest.raises(IntegrityError, match="contributor authority is invalid"):
        postgres_session.flush()
