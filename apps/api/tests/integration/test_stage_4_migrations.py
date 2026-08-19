import re
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.db.session import EXPECTED_SCHEMA_REVISION
from sqlalchemy import Engine, inspect, text

from tests.integration.conftest import (
    assert_connection_targets_guarded_database,
    truncate_application_tables,
)

pytestmark = pytest.mark.integration


def _alembic_config(connection) -> Config:  # type: ignore[no-untyped-def]
    config = Config("alembic.ini")
    config.attributes["connection"] = connection
    return config


def test_populated_0002_upgrade_backfills_and_preserves_stage_4_state(
    postgres_engine: Engine,
    integration_settings: Settings,
) -> None:
    truncate_application_tables(postgres_engine, integration_settings)
    original_key = "legacy-plaintext-placeholder"
    occurred_at = datetime(2026, 1, 1, tzinfo=UTC)

    try:
        with postgres_engine.connect() as connection:
            assert_connection_targets_guarded_database(connection, integration_settings)
            connection.rollback()
            config = _alembic_config(connection)
            command.downgrade(config, "0002_stage_1_integrity_hardening")

            user_id = connection.scalar(
                text("INSERT INTO users (anonymous_key) VALUES (:key) RETURNING id"),
                {"key": original_key},
            )
            game_id = connection.scalar(
                text(
                    """
                    INSERT INTO games (title, slug, description)
                    VALUES ('Legacy Game', 'legacy-game', 'Migration fixture')
                    RETURNING id
                    """
                )
            )
            assert user_id is not None
            assert game_id is not None
            connection.execute(
                text(
                    """
                    INSERT INTO user_preferences (user_id, preference_type, value, weight)
                    VALUES (:user_id, 'genre', 'strategy', 1)
                    """
                ),
                {"user_id": user_id},
            )
            for interaction_type, timestamp in (
                ("liked", occurred_at),
                ("disliked", occurred_at),
                ("liked", occurred_at + timedelta(hours=1)),
                ("played", occurred_at),
                ("played", occurred_at + timedelta(hours=2)),
            ):
                connection.execute(
                    text(
                        """
                        INSERT INTO interactions (
                            user_id, game_id, interaction_type, value, occurred_at
                        ) VALUES (:user_id, :game_id, :interaction_type, NULL, :occurred_at)
                        """
                    ),
                    {
                        "user_id": user_id,
                        "game_id": game_id,
                        "interaction_type": interaction_type,
                        "occurred_at": timestamp,
                    },
                )
            connection.execute(
                text(
                    """
                    INSERT INTO recommendation_events (
                        user_id, model_name, model_version, request_context, result_summary
                    ) VALUES (
                        :user_id, 'legacy-model', '1',
                        CAST(:request_context AS jsonb), CAST(:result_summary AS jsonb)
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "request_context": "{}",
                    "result_summary": "[]",
                },
            )
            connection.commit()

            command.upgrade(config, "head")
            command.check(config)

            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                EXPECTED_SCHEMA_REVISION
            )
            user = (
                connection.execute(
                    text(
                        """
                    SELECT anonymous_token_digest, consent_version, consented_at,
                           expires_at, revoked_at
                    FROM users
                    WHERE id = :user_id
                    """
                    ),
                    {"user_id": user_id},
                )
                .mappings()
                .one()
            )
            assert re.fullmatch(r"[0-9a-f]{64}", user["anonymous_token_digest"])
            assert original_key not in user["anonymous_token_digest"]
            assert user["consent_version"] is None
            assert user["consented_at"] is None
            assert user["expires_at"] is None
            assert user["revoked_at"] is not None
            assert "anonymous_key" not in {
                column["name"] for column in inspect(connection).get_columns("users")
            }

            interactions = (
                connection.execute(
                    text(
                        """
                    SELECT id, interaction_type, occurred_at, superseded_at
                    FROM interactions
                    ORDER BY id
                    """
                    )
                )
                .mappings()
                .all()
            )
            active_reactions = [
                row
                for row in interactions
                if row["interaction_type"] in {"liked", "disliked"} and row["superseded_at"] is None
            ]
            active_played = [
                row
                for row in interactions
                if row["interaction_type"] == "played" and row["superseded_at"] is None
            ]
            assert len(active_reactions) == 1
            assert active_reactions[0]["occurred_at"] == occurred_at + timedelta(hours=1)
            assert len(active_played) == 1
            assert active_played[0]["occurred_at"] == occurred_at + timedelta(hours=2)
            assert all(
                row["superseded_at"] is None or row["superseded_at"] >= row["occurred_at"]
                for row in interactions
            )

            event = (
                connection.execute(
                    text(
                        """
                    SELECT generation_id, event_schema_version, data_fingerprint,
                           ranking_policy_name, ranking_policy_version
                    FROM recommendation_events
                    """
                    )
                )
                .mappings()
                .one()
            )
            assert event == {
                "generation_id": "legacy-1",
                "event_schema_version": "legacy-v1",
                "data_fingerprint": None,
                "ranking_policy_name": None,
                "ranking_policy_version": None,
            }
            assert connection.scalar(text("SELECT count(*) FROM user_preferences")) == 1
            assert connection.scalar(text("SELECT count(*) FROM games")) == 1
            connection.rollback()

            command.downgrade(config, "0002_stage_1_integrity_hardening")
            downgraded_key = connection.scalar(
                text("SELECT anonymous_key FROM users WHERE id = :user_id"),
                {"user_id": user_id},
            )
            assert downgraded_key == f"stage4-downgrade-{user_id}"
            assert downgraded_key != original_key
            connection.rollback()

            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                EXPECTED_SCHEMA_REVISION
            )
            assert connection.scalar(text("SELECT count(*) FROM users")) == 1
            assert connection.scalar(text("SELECT count(*) FROM interactions")) == 5
            assert connection.scalar(text("SELECT count(*) FROM recommendation_events")) == 1
            connection.rollback()
    finally:
        with postgres_engine.connect() as connection:
            assert_connection_targets_guarded_database(connection, integration_settings)
            connection.rollback()
            command.upgrade(_alembic_config(connection), "head")
        truncate_application_tables(postgres_engine, integration_settings)
