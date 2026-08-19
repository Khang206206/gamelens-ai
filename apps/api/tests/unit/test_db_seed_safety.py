import json
from copy import deepcopy

import pytest
from app.core.config import Settings
from app.db.models import InteractionType, PreferenceType
from app.db.seed import DEFAULT_SEED_PATH, SeedFile
from pydantic import ValidationError

from tests.conftest import validate_test_database_reset


def make_guarded_settings(
    database_url: str = (
        "postgresql+psycopg://gamelens_test:gamelens_test_only@localhost:5433/gamelens_test"
    ),
    *,
    environment: str = "test",
) -> Settings:
    return Settings(
        _env_file=None,
        app_name="GameLens AI API",
        environment=environment,
        api_host="127.0.0.1",
        api_port=8000,
        database_url=database_url,
        cors_origins=["http://testserver"],
        anonymous_session_cookie_secure=environment != "test",
        log_level="WARNING",
    )


def load_raw_seed() -> dict[str, object]:
    return json.loads(DEFAULT_SEED_PATH.read_text(encoding="utf-8"))


def test_destructive_database_guard_accepts_only_explicit_test_target() -> None:
    validate_test_database_reset(
        make_guarded_settings(),
        process_environment="test",
        allow_reset="true",
    )


@pytest.mark.parametrize(
    ("settings", "process_environment", "allow_reset", "expected"),
    [
        (make_guarded_settings(environment="development"), "test", "true", "settings.environment"),
        (make_guarded_settings(), "development", "true", "process ENVIRONMENT"),
        (make_guarded_settings(), "test", "True", "ALLOW_TEST_DATABASE_RESET"),
        (
            make_guarded_settings("postgresql+psycopg://user:password@localhost:5432/gamelens"),
            "test",
            "true",
            "must end with '_test'",
        ),
        (
            make_guarded_settings("postgresql+psycopg://user:password@db:5432/gamelens_test"),
            "test",
            "true",
            "host is not",
        ),
    ],
)
def test_destructive_database_guard_fails_closed(
    settings: Settings,
    process_environment: str,
    allow_reset: str,
    expected: str,
) -> None:
    with pytest.raises(RuntimeError, match=expected):
        validate_test_database_reset(
            settings,
            process_environment=process_environment,
            allow_reset=allow_reset,
        )


def test_seed_schema_forbids_unknown_fields() -> None:
    raw_seed = load_raw_seed()
    games = raw_seed["games"]
    assert isinstance(games, list)
    games[0]["rating_counts"] = games[0]["rating_count"]

    with pytest.raises(ValidationError, match="extra_forbidden"):
        SeedFile.model_validate(raw_seed)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("external_id", "x" * 101),
        ("slug", "a" * 221),
        ("cover_image_url", "x" * 1001),
        ("average_rating", "8.123"),
        ("popularity_score", "1.12345"),
        ("popularity_score", "1000000.0000"),
    ],
)
def test_seed_game_fields_match_database_limits(field_name: str, value: str) -> None:
    raw_seed = load_raw_seed()
    games = raw_seed["games"]
    assert isinstance(games, list)
    games[0][field_name] = value

    with pytest.raises(ValidationError):
        SeedFile.model_validate(raw_seed)


def test_seed_taxonomy_slug_matches_database_length() -> None:
    raw_seed = load_raw_seed()
    taxonomies = raw_seed["taxonomies"]
    assert isinstance(taxonomies, dict)
    genres = taxonomies["genres"]
    assert isinstance(genres, list)
    genres[0]["slug"] = "a" * 101

    with pytest.raises(ValidationError):
        SeedFile.model_validate(raw_seed)


@pytest.mark.parametrize("field_name", ["genre_slugs", "tag_slugs", "platform_slugs"])
def test_seed_rejects_duplicate_game_taxonomy_references(field_name: str) -> None:
    raw_seed = deepcopy(load_raw_seed())
    games = raw_seed["games"]
    assert isinstance(games, list)
    values = games[0][field_name]
    assert isinstance(values, list)
    values.append(values[0])

    with pytest.raises(ValidationError, match="must not contain duplicate slugs"):
        SeedFile.model_validate(raw_seed)


def test_application_enums_match_database_contract() -> None:
    assert {item.value for item in PreferenceType} == {"genre", "tag", "platform", "game"}
    assert {item.value for item in InteractionType} == {
        "viewed",
        "liked",
        "disliked",
        "played",
        "wishlisted",
        "rated",
    }
