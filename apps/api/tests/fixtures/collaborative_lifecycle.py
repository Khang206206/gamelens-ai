from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from app.commands.operator_safety import (
    resolved_database_identity,
    validate_test_execution_configuration,
)
from app.commands.output import fail_command, write_json
from app.core.config import Settings
from app.core.security import parse_session_credential
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeContributionConsent,
    Game,
    Interaction,
    InteractionType,
    PreferenceType,
    RecommendationEvent,
    User,
    UserPreference,
)
from app.db.session import begin_repeatable_read, create_database_engine
from sqlalchemy import Connection, Engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

SCENARIO_NAME = "stage-5-disposable-lifecycle-v1"
PERSONALIZATION_CONSENT_VERSION = "stage-4-v1"
OUTDATED_PERSONALIZATION_CONSENT_VERSION = "stage-4-test-outdated-v0"
CONTRIBUTION_CONSENT_VERSION = "stage-5-contribution-v1"
MAX_LINKED_SESSIONS = 8

# This cohort is project-authored synthetic test data. It contains no real user data and is
# structural lifecycle evidence only; it is not representativeness or recommendation-quality
# evidence. The positive profiles intentionally mirror the committed Stage 5 fixture contract.
PROVENANCE = {
    "kind": "project-authored",
    "contains_real_user_data": False,
    "quality_evidence": False,
}


class ScenarioControlError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _Role:
    name: str
    positive_game_slugs: tuple[str, ...]
    authority: Literal["current", "expired", "revoked", "outdated"] = "current"


_SUPPORTED_PROFILES = (
    ("emberfall-tactics", "neon-drift-circuit", "verdant-vale"),
    ("clockwork-orchard", "emberfall-tactics", "neon-drift-circuit"),
    ("clockwork-orchard", "emberfall-tactics", "verdant-vale"),
    ("clockwork-orchard", "neon-drift-circuit", "verdant-vale"),
    ("emberfall-tactics", "neon-drift-circuit", "starbound-couriers"),
    ("emberfall-tactics", "starbound-couriers", "verdant-vale"),
    ("neon-drift-circuit", "starbound-couriers", "verdant-vale"),
    ("clockwork-orchard", "emberfall-tactics", "starbound-couriers"),
    ("clockwork-orchard", "neon-drift-circuit", "starbound-couriers"),
    ("clockwork-orchard", "starbound-couriers", "verdant-vale"),
    ("emberfall-tactics", "neon-drift-circuit", "paper-kingdoms"),
    ("paper-kingdoms", "starbound-couriers", "verdant-vale"),
)
_EXCLUDED_PROFILE = _SUPPORTED_PROFILES[0]
_ROLES = tuple(
    _Role(f"supported-{index:02d}", profile)
    for index, profile in enumerate(_SUPPORTED_PROFILES, start=1)
) + (
    _Role("expired", _EXCLUDED_PROFILE, "expired"),
    _Role("revoked", _EXCLUDED_PROFILE, "revoked"),
    _Role("outdated", _EXCLUDED_PROFILE, "outdated"),
    _Role("negative", ()),
    _Role("pruned", ("harborlight", "lumen-depths")),
)
_EXPECTED_USER_COUNT = len(_ROLES)
_EXPECTED_CONTRIBUTION_COUNT = len(_ROLES)
_EXPECTED_PREFERENCE_COUNT = sum(len(role.positive_game_slugs) for role in _ROLES)
_EXPECTED_INTERACTION_COUNT = 2
_REQUIRED_GAME_SLUGS = frozenset(slug for role in _ROLES for slug in role.positive_game_slugs) | {
    "abyssal-signal",
    "warden-of-glass",
}


def _role_digest(role_name: str) -> str:
    value = f"gamelens:{SCENARIO_NAME}:{role_name}"
    return hashlib.sha256(value.encode()).hexdigest()


def _scenario_digests() -> tuple[str, ...]:
    return tuple(_role_digest(role.name) for role in _ROLES)


class DisposableCollaborativeScenario:
    """Bounded, private control surface for the disposable Stage 5 lifecycle cohort."""

    def __init__(
        self,
        engine: Engine,
        settings: Settings,
        *,
        process_environment: str | None,
        allow_test_reset: str | None,
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._process_environment = process_environment
        self._allow_test_reset = allow_test_reset

    def create_cohort(self, *, scenario: str) -> dict[str, object]:
        self._require_named_scenario(scenario)
        with self._write_session() as session:
            now = session.scalar(select(func.clock_timestamp()))
            assert now is not None
            state = self._scenario_state(session)
            if state == "complete":
                raise ScenarioControlError(
                    "scenario_already_exists",
                    "The named disposable cohort already exists",
                )
            if state == "partial":
                raise ScenarioControlError(
                    "scenario_incomplete",
                    "The named disposable cohort is partial; refusing implicit repair",
                )

            games = {
                game.slug: game
                for game in session.scalars(select(Game).where(Game.slug.in_(_REQUIRED_GAME_SLUGS)))
            }
            if set(games) != set(_REQUIRED_GAME_SLUGS):
                raise ScenarioControlError(
                    "catalog_not_seeded",
                    "The existing catalog does not contain the scenario games",
                )

            users_by_role: dict[str, User] = {}
            for role in _ROLES:
                consent_version = (
                    OUTDATED_PERSONALIZATION_CONSENT_VERSION
                    if role.authority == "outdated"
                    else PERSONALIZATION_CONSENT_VERSION
                )
                user = User(
                    anonymous_token_digest=_role_digest(role.name),
                    consent_version=consent_version,
                    consented_at=now - timedelta(days=10),
                    expires_at=(
                        now - timedelta(days=1)
                        if role.authority == "expired"
                        else now + timedelta(days=90)
                    ),
                    revoked_at=(now - timedelta(days=1) if role.authority == "revoked" else None),
                )
                session.add(user)
                users_by_role[role.name] = user
            session.flush()

            session.add_all(
                CollaborativeContributionConsent(
                    user_id=user.id,
                    consent_version=CONTRIBUTION_CONSENT_VERSION,
                    granted_at=now - timedelta(days=5),
                )
                for user in users_by_role.values()
            )
            session.add_all(
                UserPreference(
                    user_id=users_by_role[role.name].id,
                    preference_type=PreferenceType.GAME,
                    value=slug,
                    weight=Decimal("1"),
                )
                for role in _ROLES
                for slug in role.positive_game_slugs
            )
            negative_user = users_by_role["negative"]
            session.add_all(
                (
                    Interaction(
                        user_id=negative_user.id,
                        game_id=games["abyssal-signal"].id,
                        interaction_type=InteractionType.DISLIKED,
                        value=None,
                        occurred_at=now - timedelta(days=2),
                    ),
                    Interaction(
                        user_id=negative_user.id,
                        game_id=games["warden-of-glass"].id,
                        interaction_type=InteractionType.RATED,
                        value=Decimal("4"),
                        occurred_at=now - timedelta(days=2),
                    ),
                )
            )
            session.flush()
            if self._scenario_state(session) != "complete":
                raise ScenarioControlError(
                    "scenario_incomplete",
                    "The named disposable cohort did not reach its complete footprint",
                )

        return self._cohort_result("created")

    def link_session(self, *, scenario: str, raw_token: str) -> dict[str, object]:
        self._require_named_scenario(scenario)
        with self._write_session() as session:
            now = session.scalar(select(func.clock_timestamp()))
            assert now is not None
            self._require_complete_scenario(session)
            user = self._locked_session_user(session, raw_token)
            if not self._personalization_is_current(user, now=now):
                raise ScenarioControlError(
                    "session_authority_invalid",
                    "The private session channel requires current personalization consent",
                )
            contribution = session.get(
                CollaborativeContributionConsent,
                user.id,
                with_for_update=True,
            )
            if contribution is not None:
                if (
                    contribution.consent_version == CONTRIBUTION_CONSENT_VERSION
                    and contribution.withdrawn_at is None
                ):
                    return self._control_result("link-session", "unchanged")
                raise ScenarioControlError(
                    "contribution_state_conflict",
                    "The session has an incompatible contribution lifecycle state",
                )

            scenario_user_ids = select(User.id).where(
                User.anonymous_token_digest.in_(_scenario_digests())
            )
            linked_count = session.scalar(
                select(func.count(CollaborativeContributionConsent.user_id)).where(
                    CollaborativeContributionConsent.user_id.not_in(scenario_user_ids)
                )
            )
            if int(linked_count or 0) >= MAX_LINKED_SESSIONS:
                raise ScenarioControlError(
                    "linked_session_limit_reached",
                    "The disposable scenario has reached its linked-session limit",
                )
            session.add(
                CollaborativeContributionConsent(
                    user_id=user.id,
                    consent_version=CONTRIBUTION_CONSENT_VERSION,
                    granted_at=now,
                )
            )
        return self._control_result("link-session", "updated")

    def arrange_outdated_consent(
        self,
        *,
        scenario: str,
        raw_token: str,
    ) -> dict[str, object]:
        self._require_named_scenario(scenario)
        with self._write_session() as session:
            now = session.scalar(select(func.clock_timestamp()))
            assert now is not None
            self._require_complete_scenario(session)
            user = self._locked_session_user(session, raw_token)
            self._require_linked_contribution(session, user)
            if user.revoked_at is not None or user.expires_at is None or user.expires_at <= now:
                raise ScenarioControlError(
                    "session_authority_invalid",
                    "The private session channel requires unexpired personalization authority",
                )
            if user.consent_version == OUTDATED_PERSONALIZATION_CONSENT_VERSION:
                return self._control_result("arrange-outdated-consent", "unchanged")
            if user.consent_version != PERSONALIZATION_CONSENT_VERSION:
                raise ScenarioControlError(
                    "session_authority_invalid",
                    "The session personalization state cannot be arranged safely",
                )
            user.consent_version = OUTDATED_PERSONALIZATION_CONSENT_VERSION
            user.consented_at = now - timedelta(days=1)
        return self._control_result("arrange-outdated-consent", "updated")

    def withdraw_contribution(
        self,
        *,
        scenario: str,
        raw_token: str,
    ) -> dict[str, object]:
        self._require_named_scenario(scenario)
        with self._write_session() as session:
            now = session.scalar(select(func.clock_timestamp()))
            assert now is not None
            self._require_complete_scenario(session)
            user = self._locked_session_user(session, raw_token)
            contribution = self._require_linked_contribution(session, user)
            if contribution.withdrawn_at is not None:
                return self._control_result("withdraw-contribution", "unchanged")
            contribution.withdrawn_at = now
        return self._control_result("withdraw-contribution", "updated")

    def inspect(
        self,
        *,
        scenario: str,
        expected_build_id: str | None = None,
        expected_build_status: str | None = None,
        expected_generation_id: str | None = None,
        expected_ranking_mode: str | None = None,
    ) -> dict[str, object]:
        self._require_named_scenario(scenario)
        if (expected_build_id is None) != (expected_build_status is None):
            raise ScenarioControlError(
                "assertion_arguments_invalid",
                "Build assertions require both an identity and expected status",
            )
        if (expected_generation_id is None) != (expected_ranking_mode is None):
            raise ScenarioControlError(
                "assertion_arguments_invalid",
                "Event assertions require both an identity and expected mode",
            )
        if expected_build_status not in {None, "active", "invalidated", "retired"}:
            raise ScenarioControlError(
                "assertion_arguments_invalid", "The expected build status is unsupported"
            )
        if expected_ranking_mode not in {None, "hybrid", "stage_4_fallback"}:
            raise ScenarioControlError(
                "assertion_arguments_invalid", "The expected ranking mode is unsupported"
            )

        with self._read_session() as session:
            self._require_complete_scenario(session)
            registry_rows = session.execute(
                select(CollaborativeArtifactBuild.status, func.count())
                .group_by(CollaborativeArtifactBuild.status)
                .order_by(CollaborativeArtifactBuild.status)
            ).all()
            event_rows = session.execute(
                select(RecommendationEvent.ranking_mode, func.count())
                .where(RecommendationEvent.event_schema_version == "stage-5-v1")
                .group_by(RecommendationEvent.ranking_mode)
                .order_by(RecommendationEvent.ranking_mode)
            ).all()
            contribution_rows = session.execute(
                select(
                    func.count(CollaborativeContributionConsent.user_id),
                    func.count(CollaborativeContributionConsent.withdrawn_at),
                )
            ).one()
            positive_preferences = session.scalar(
                select(func.count(UserPreference.id)).where(
                    UserPreference.preference_type == PreferenceType.GAME,
                    UserPreference.weight > 0,
                )
            )

            build_matches: bool | None = None
            if expected_build_id is not None:
                build_matches = (
                    session.scalar(
                        select(func.count(CollaborativeArtifactBuild.build_id)).where(
                            CollaborativeArtifactBuild.build_id == expected_build_id,
                            CollaborativeArtifactBuild.status == expected_build_status,
                        )
                    )
                    == 1
                )
            event_matches: bool | None = None
            if expected_generation_id is not None:
                event_matches = (
                    session.scalar(
                        select(func.count(RecommendationEvent.id)).where(
                            RecommendationEvent.generation_id == expected_generation_id,
                            RecommendationEvent.event_schema_version == "stage-5-v1",
                            RecommendationEvent.ranking_mode == expected_ranking_mode,
                        )
                    )
                    == 1
                )
            if build_matches is False or event_matches is False:
                raise ScenarioControlError(
                    "scenario_assertion_failed",
                    "A requested aggregate registry or event assertion did not match",
                )

        return {
            "scenario": SCENARIO_NAME,
            "status": "inspected",
            "provenance": PROVENANCE,
            "cohort": {
                "defined_profiles": _EXPECTED_USER_COUNT,
                "supported_profiles": len(_SUPPORTED_PROFILES),
                "positive_preferences": int(positive_preferences or 0),
                "contribution_rows": int(contribution_rows[0]),
                "withdrawn_contribution_rows": int(contribution_rows[1]),
            },
            "registry": {
                "total": sum(count for _status, count in registry_rows),
                "by_status": {status: count for status, count in registry_rows},
                "expected_status_matches": build_matches,
            },
            "events": {
                "stage_5_total": sum(count for _mode, count in event_rows),
                "by_ranking_mode": {str(mode): count for mode, count in event_rows},
                "expected_mode_matches": event_matches,
            },
            "privacy": {
                "aggregate_only": True,
                "identity_fields_emitted": False,
                "cohort_mapping_emitted": False,
            },
        }

    def _scenario_state(self, session: Session) -> Literal["absent", "partial", "complete"]:
        users = list(
            session.scalars(
                select(User).where(User.anonymous_token_digest.in_(_scenario_digests()))
            )
        )
        if not users:
            return "absent"
        if len(users) != _EXPECTED_USER_COUNT:
            return "partial"

        now = session.scalar(select(func.clock_timestamp()))
        assert now is not None
        users_by_digest = {user.anonymous_token_digest: user for user in users}
        users_by_role: dict[str, User] = {}
        for role in _ROLES:
            user = users_by_digest.get(_role_digest(role.name))
            expected_version = (
                OUTDATED_PERSONALIZATION_CONSENT_VERSION
                if role.authority == "outdated"
                else PERSONALIZATION_CONSENT_VERSION
            )
            if (
                user is None
                or user.consent_version != expected_version
                or user.consented_at is None
                or user.expires_at is None
                or (role.authority == "expired") != (user.expires_at <= now)
                or (role.authority == "revoked") != (user.revoked_at is not None)
            ):
                return "partial"
            users_by_role[role.name] = user

        user_ids = tuple(user.id for user in users_by_role.values())
        contributions = list(
            session.scalars(
                select(CollaborativeContributionConsent).where(
                    CollaborativeContributionConsent.user_id.in_(user_ids)
                )
            )
        )
        if len(contributions) != _EXPECTED_CONTRIBUTION_COUNT or any(
            contribution.consent_version != CONTRIBUTION_CONSENT_VERSION
            or contribution.granted_at > now
            or contribution.withdrawn_at is not None
            for contribution in contributions
        ):
            return "partial"

        preferences = set(
            session.execute(
                select(
                    UserPreference.user_id,
                    UserPreference.preference_type,
                    UserPreference.value,
                    UserPreference.weight,
                ).where(UserPreference.user_id.in_(user_ids))
            ).all()
        )
        expected_preferences = {
            (
                users_by_role[role.name].id,
                PreferenceType.GAME,
                slug,
                Decimal("1"),
            )
            for role in _ROLES
            for slug in role.positive_game_slugs
        }
        if preferences != expected_preferences:
            return "partial"

        interactions = set(
            session.execute(
                select(
                    Interaction.user_id,
                    Game.slug,
                    Interaction.interaction_type,
                    Interaction.value,
                    Interaction.superseded_at,
                )
                .join(Game, Game.id == Interaction.game_id)
                .where(Interaction.user_id.in_(user_ids))
            ).all()
        )
        expected_interactions = {
            (
                users_by_role["negative"].id,
                "abyssal-signal",
                InteractionType.DISLIKED,
                None,
                None,
            ),
            (
                users_by_role["negative"].id,
                "warden-of-glass",
                InteractionType.RATED,
                Decimal("4"),
                None,
            ),
        }
        return "complete" if interactions == expected_interactions else "partial"

    def _require_complete_scenario(self, session: Session) -> None:
        state = self._scenario_state(session)
        if state == "absent":
            raise ScenarioControlError(
                "scenario_missing", "The named disposable cohort has not been created"
            )
        if state != "complete":
            raise ScenarioControlError(
                "scenario_incomplete",
                "The named disposable cohort is partial; refusing implicit repair",
            )

    def _locked_session_user(self, session: Session, raw_token: str) -> User:
        credential = parse_session_credential(self._settings, raw_token)
        if credential is None:
            raise ScenarioControlError(
                "session_credential_invalid", "The private session credential is invalid"
            )
        user = session.scalar(
            select(User).where(User.anonymous_token_digest == credential.digest).with_for_update()
        )
        if user is None or user.anonymous_token_digest in _scenario_digests():
            raise ScenarioControlError(
                "session_not_found", "The private session does not identify a linkable session"
            )
        return user

    @staticmethod
    def _personalization_is_current(user: User, *, now: datetime) -> bool:
        return (
            user.consent_version == PERSONALIZATION_CONSENT_VERSION
            and user.consented_at is not None
            and user.consented_at <= now
            and user.expires_at is not None
            and user.expires_at > now
            and (user.revoked_at is None or user.revoked_at > now)
        )

    @staticmethod
    def _require_linked_contribution(
        session: Session,
        user: User,
    ) -> CollaborativeContributionConsent:
        contribution = session.get(
            CollaborativeContributionConsent,
            user.id,
            with_for_update=True,
        )
        if contribution is None or contribution.consent_version != CONTRIBUTION_CONSENT_VERSION:
            raise ScenarioControlError(
                "session_not_linked",
                "The private session is not linked to the disposable cohort",
            )
        return contribution

    @staticmethod
    def _require_named_scenario(scenario: str) -> None:
        if scenario != SCENARIO_NAME:
            raise ScenarioControlError(
                "scenario_unknown", "The requested disposable scenario is not supported"
            )

    @staticmethod
    def _cohort_result(status: str) -> dict[str, object]:
        return {
            "scenario": SCENARIO_NAME,
            "status": status,
            "provenance": PROVENANCE,
            "cohort": {
                "defined_profiles": _EXPECTED_USER_COUNT,
                "supported_profiles": len(_SUPPORTED_PROFILES),
                "positive_preferences": _EXPECTED_PREFERENCE_COUNT,
                "negative_signals": _EXPECTED_INTERACTION_COUNT,
            },
            "privacy": {
                "aggregate_only": True,
                "identity_fields_emitted": False,
                "cohort_mapping_emitted": False,
            },
        }

    @staticmethod
    def _control_result(operation: str, status: str) -> dict[str, object]:
        return {
            "scenario": SCENARIO_NAME,
            "operation": operation,
            "status": status,
            "privacy": {
                "aggregate_only": True,
                "identity_fields_emitted": False,
                "cohort_mapping_emitted": False,
            },
        }

    def _validate_configuration(self) -> None:
        try:
            validate_test_execution_configuration(
                self._settings.database_url,
                settings_environment=self._settings.environment,
                process_environment=self._process_environment,
                allow_test_reset=self._allow_test_reset,
            )
        except RuntimeError as error:
            raise ScenarioControlError(
                "unsafe_test_database",
                "The disposable scenario requires explicit guarded test database settings",
            ) from error
        if self._engine.url != make_url(self._settings.database_url):
            raise ScenarioControlError(
                "database_connection_mismatch",
                "The connected engine does not match the guarded test database setting",
            )

    def _validate_connection(self, connection: Connection) -> None:
        row = (
            connection.execute(
                text(
                    """
                SELECT current_database() AS database_name,
                       current_schema() AS schema_name,
                       inet_server_addr()::text AS server_address,
                       inet_server_port() AS server_port
                """
                )
            )
            .mappings()
            .one()
        )
        try:
            identity = resolved_database_identity(
                self._settings.database_url,
                server_address=row["server_address"],
                server_port=row["server_port"],
                database=row["database_name"],
                schema=row["schema_name"],
            )
        except RuntimeError as error:
            raise ScenarioControlError(
                "database_connection_mismatch",
                "The actual PostgreSQL identity does not match the guarded test database",
            ) from error
        if identity.schema != "public":
            raise ScenarioControlError(
                "database_schema_unsafe",
                "The disposable scenario requires the public test schema",
            )

    @contextmanager
    def _write_session(self) -> Iterator[Session]:
        self._validate_configuration()
        with self._engine.begin() as connection:
            self._validate_connection(connection)
            session = Session(bind=connection, autoflush=False, expire_on_commit=False)
            try:
                yield session
                session.flush()
            finally:
                session.close()

    @contextmanager
    def _read_session(self) -> Iterator[Session]:
        self._validate_configuration()
        with self._engine.connect() as connection:
            self._validate_connection(connection)
            connection.rollback()
            session = Session(bind=connection, autoflush=False, expire_on_commit=False)
            begin_repeatable_read(session, read_only=True)
            try:
                yield session
            finally:
                session.rollback()
                session.close()


def _controller_from_environment() -> tuple[DisposableCollaborativeScenario, Engine]:
    database_url = os.environ.get("GAMELENS_TEST_DATABASE_URL")
    if database_url is None:
        raise ScenarioControlError(
            "test_database_required",
            "GAMELENS_TEST_DATABASE_URL is required; no fallback database is allowed",
        )
    settings = Settings(
        _env_file=None,
        environment=os.environ.get("ENVIRONMENT", "development"),
        database_url=database_url,
        cors_origins=["http://testserver"],
        collaborative_live_data_enabled=False,
        collaborative_contribution_consent_version=None,
        collaborative_live_promotion_enabled=False,
        collaborative_allow_test_fixture=False,
    )
    engine = create_database_engine(database_url)
    return (
        DisposableCollaborativeScenario(
            engine,
            settings,
            process_environment=os.environ.get("ENVIRONMENT"),
            allow_test_reset=os.environ.get("GAMELENS_ALLOW_TEST_DATABASE_RESET"),
        ),
        engine,
    )


def _read_private_token() -> str:
    raw_token = sys.stdin.readline().strip()
    if not raw_token:
        raise ScenarioControlError(
            "session_credential_required",
            "A private session credential must be provided on stdin",
        )
    return raw_token


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Control one guarded disposable Stage 5 lifecycle cohort"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "create-cohort",
        "link-session",
        "arrange-outdated-consent",
        "withdraw-contribution",
    ):
        command_parser = commands.add_parser(name)
        command_parser.add_argument("--scenario", choices=(SCENARIO_NAME,), required=True)
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("--scenario", choices=(SCENARIO_NAME,), required=True)
    inspect_parser.add_argument("--expected-build-id")
    inspect_parser.add_argument(
        "--expected-build-status", choices=("active", "invalidated", "retired")
    )
    inspect_parser.add_argument("--expected-generation-id")
    inspect_parser.add_argument("--expected-ranking-mode", choices=("hybrid", "stage_4_fallback"))
    args = parser.parse_args()

    engine: Engine | None = None
    try:
        controller, engine = _controller_from_environment()
        if args.command == "create-cohort":
            result = controller.create_cohort(scenario=args.scenario)
        elif args.command == "link-session":
            result = controller.link_session(
                scenario=args.scenario,
                raw_token=_read_private_token(),
            )
        elif args.command == "arrange-outdated-consent":
            result = controller.arrange_outdated_consent(
                scenario=args.scenario,
                raw_token=_read_private_token(),
            )
        elif args.command == "withdraw-contribution":
            result = controller.withdraw_contribution(
                scenario=args.scenario,
                raw_token=_read_private_token(),
            )
        else:
            result = controller.inspect(
                scenario=args.scenario,
                expected_build_id=args.expected_build_id,
                expected_build_status=args.expected_build_status,
                expected_generation_id=args.expected_generation_id,
                expected_ranking_mode=args.expected_ranking_mode,
            )
    except (ScenarioControlError, SQLAlchemyError, ValueError) as error:
        if isinstance(error, ScenarioControlError):
            fail_command(error, fallback_code=error.code)
        fail_command(
            ScenarioControlError(
                "scenario_database_failed",
                "The disposable scenario database operation failed safely",
            ),
            fallback_code="scenario_database_failed",
        )
    finally:
        if engine is not None:
            engine.dispose()
    write_json(result)


if __name__ == "__main__":
    main()
