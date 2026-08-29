from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

import pytest
from app.commands.collaborative_artifact import build_fixture_artifact
from app.core.config import PROJECT_ROOT, Settings
from app.services.recommendation import (
    COLLABORATIVE_READINESS_REASONS,
    CollaborativeArtifactComponent,
    CollaborativeReadiness,
    CollaborativeReadinessRow,
    create_collaborative_component,
    evaluate_collaborative_readiness,
)
from gamelens_recommender import (
    COLLABORATIVE_UNAVAILABLE_REASONS,
    LoadedCollaborativeArtifact,
)

NOW = datetime(2026, 8, 29, 12, tzinfo=UTC)
VALID_UNTIL = datetime(2026, 9, 29, 12, tzinfo=UTC)
CATALOG_FINGERPRINT = "a" * 64
INTERACTION_FINGERPRINT = "b" * 64
CONSENT_VERSION = "stage-5-contribution-v1"
BUILD_ID = "stage5-live-build-v1"
FIXTURE_PATH = (
    PROJECT_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "games.json"


def _fake_artifact(
    source_kind: Literal["fixture", "live"] = "live",
    *,
    build_id: object = BUILD_ID,
    data_revision: object = 7,
    consent_version: object = CONSENT_VERSION,
    catalog_fingerprint: object = CATALOG_FINGERPRINT,
    interaction_fingerprint: object = INTERACTION_FINGERPRINT,
    valid_until: object = "2026-09-29T12:00:00.000000Z",
    contributor_count: object = 12,
    retained_positive_edges: object = 36,
    retained_items: object = 6,
) -> LoadedCollaborativeArtifact:
    if source_kind == "fixture":
        data_revision = None
        consent_version = None
    manifest = {
        "source": {"kind": source_kind},
        "build": {"id": build_id},
        "lifecycle": {
            "data_revision": data_revision,
            "consent_version": consent_version,
            "valid_until": valid_until,
        },
        "catalog_fingerprint": catalog_fingerprint,
        "interaction_fingerprint": interaction_fingerprint,
        "matrix": {
            "retained_contributors": contributor_count,
            "retained_positive_edges": retained_positive_edges,
            "retained_items": retained_items,
        },
        "thresholds": {
            "activation_minimum_users": 10,
            "activation_minimum_edges": 20,
            "activation_minimum_items": 5,
        },
    }
    return cast(LoadedCollaborativeArtifact, SimpleNamespace(manifest=manifest))


def _component(
    source_kind: Literal["fixture", "live"] = "live",
    **artifact_changes: object,
) -> CollaborativeArtifactComponent:
    artifact = _fake_artifact(source_kind, **artifact_changes)
    return CollaborativeArtifactComponent.loaded(
        artifact,
        source_kind=source_kind,
    )


def _lineage(**changes: object) -> CollaborativeReadinessRow:
    row = CollaborativeReadinessRow(
        build_id=BUILD_ID,
        source_kind="live",
        status="active",
        registered_revision=7,
        invalidation_epoch=0,
        contributor_count=12,
        consent_version=CONSENT_VERSION,
        catalog_fingerprint=CATALOG_FINGERPRINT,
        interaction_fingerprint=INTERACTION_FINGERPRINT,
        valid_until=VALID_UNTIL,
    )
    return replace(row, **changes)


def _evaluate(
    component: CollaborativeArtifactComponent,
    *,
    lineage: CollaborativeReadinessRow | None = None,
    catalog_fingerprint: str = CATALOG_FINGERPRINT,
    current_consent_version: str | None = CONSENT_VERSION,
    now: datetime = NOW,
) -> CollaborativeReadiness:
    return evaluate_collaborative_readiness(
        component,
        catalog_fingerprint=catalog_fingerprint,
        current_consent_version=current_consent_version,
        now=now,
        lineage=lineage,
    )


def test_readiness_reasons_are_exactly_compatible_with_the_hybrid_policy() -> None:
    assert COLLABORATIVE_READINESS_REASONS == COLLABORATIVE_UNAVAILABLE_REASONS


def test_not_configured_is_an_immutable_unusable_decision() -> None:
    readiness = _evaluate(CollaborativeArtifactComponent.not_configured())

    assert readiness.state == "not_configured"
    assert readiness.reason == "not_configured"
    assert readiness.source_kind is None
    assert readiness.artifact is None
    assert not readiness.usable
    with pytest.raises(FrozenInstanceError):
        readiness.state = "ready"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("reason", "expected_state"),
    [
        ("fixture_not_allowed", "unavailable"),
        ("artifact_missing", "unavailable"),
        ("artifact_corrupt", "unavailable"),
        ("artifact_incompatible", "stale"),
        ("artifact_stale", "stale"),
        ("privacy_invalid", "stale"),
        ("artifact_expired", "stale"),
        ("catalog_stale", "stale"),
    ],
)
def test_intrinsic_loader_failures_map_to_bounded_readiness_states(
    reason: str,
    expected_state: str,
) -> None:
    component = CollaborativeArtifactComponent.unavailable(reason)  # type: ignore[arg-type]

    readiness = _evaluate(component)

    assert readiness.state == expected_state
    assert readiness.reason == reason
    assert readiness.artifact is None
    assert not readiness.usable


def test_guarded_fixture_is_usable_but_never_presented_as_live_ready() -> None:
    component = _component("fixture")

    readiness = _evaluate(
        component,
        lineage=None,
        current_consent_version=None,
    )

    assert readiness.state == "fixture_only"
    assert readiness.reason is None
    assert readiness.source_kind == "fixture"
    assert readiness.artifact is component.artifact
    assert readiness.usable
    assert str(component.artifact) not in repr(readiness)


def test_real_guarded_fixture_handoff_from_loader_is_fixture_only(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "readiness-fixture"
    fixture_settings = test_settings.model_copy(
        update={
            "collaborative_allow_test_fixture": True,
            "collaborative_artifact_path": artifact_path,
        }
    )
    build_fixture_artifact(
        fixture_settings,
        artifact_path,
        fixture_path=FIXTURE_PATH,
        catalog_path=CATALOG_PATH,
        built_at=NOW,
    )
    component = create_collaborative_component(
        artifact_path,
        environment="test",
        allow_test_fixture=True,
    )
    assert component.artifact is not None

    readiness = evaluate_collaborative_readiness(
        component,
        catalog_fingerprint=component.artifact.catalog_fingerprint,
        current_consent_version=None,
        now=NOW,
    )

    assert readiness.state == "fixture_only"
    assert readiness.reason is None
    assert readiness.artifact is component.artifact
    assert readiness.usable


@pytest.mark.parametrize(
    "artifact_changes",
    [
        {"contributor_count": 9},
        {"retained_positive_edges": 19},
        {"retained_items": 4},
    ],
)
def test_artifact_below_any_activation_minimum_is_insufficient_data(
    artifact_changes: dict[str, object],
) -> None:
    readiness = _evaluate(_component("fixture", **artifact_changes))

    assert readiness.state == "insufficient_data"
    assert readiness.reason == "insufficient_data"
    assert readiness.source_kind == "fixture"
    assert not readiness.usable


def test_catalog_and_time_are_rechecked_at_the_request_boundary() -> None:
    component = _component("fixture")

    catalog_stale = _evaluate(component, catalog_fingerprint="c" * 64)
    expired = _evaluate(component, now=VALID_UNTIL)

    assert (catalog_stale.state, catalog_stale.reason) == ("stale", "catalog_stale")
    assert (expired.state, expired.reason) == ("stale", "artifact_expired")


@pytest.mark.parametrize(
    "artifact_changes",
    [
        {"build_id": ""},
        {"data_revision": True},
        {"valid_until": "not-a-timestamp"},
        {"catalog_fingerprint": "not-a-fingerprint"},
        {"contributor_count": "12"},
    ],
)
def test_malformed_loaded_metadata_fails_closed_without_an_exception(
    artifact_changes: dict[str, object],
) -> None:
    readiness = _evaluate(_component("live", **artifact_changes), lineage=_lineage())

    assert readiness.state == "stale"
    assert readiness.reason == "artifact_incompatible"
    assert not readiness.usable


def test_live_artifact_without_one_matching_lineage_row_is_privacy_invalid() -> None:
    readiness = _evaluate(_component("live"), lineage=None)

    assert readiness.state == "stale"
    assert readiness.reason == "privacy_invalid"
    assert readiness.source_kind == "live"
    assert not readiness.usable


def test_matching_live_artifact_and_lineage_are_ready() -> None:
    component = _component("live")
    lineage = _lineage()

    readiness = _evaluate(component, lineage=lineage)

    assert readiness.state == "ready"
    assert readiness.reason is None
    assert readiness.source_kind == "live"
    assert readiness.artifact is component.artifact
    assert readiness.usable
    with pytest.raises(FrozenInstanceError):
        lineage.status = "retired"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("lineage_changes", "expected_reason"),
    [
        ({"status": "retired"}, "artifact_retired"),
        ({"status": "invalidated"}, "privacy_invalid"),
        ({"invalidation_epoch": 1}, "privacy_invalid"),
        ({"build_id": "different-live-build"}, "artifact_stale"),
        ({"registered_revision": 8}, "artifact_stale"),
        ({"contributor_count": 11}, "privacy_invalid"),
        ({"interaction_fingerprint": "c" * 64}, "privacy_invalid"),
        ({"consent_version": "stage-5-contribution-v2"}, "privacy_invalid"),
        ({"catalog_fingerprint": "c" * 64}, "catalog_stale"),
        ({"valid_until": VALID_UNTIL + timedelta(days=1)}, "artifact_stale"),
    ],
)
def test_every_live_lineage_mismatch_fails_closed(
    lineage_changes: dict[str, object],
    expected_reason: str,
) -> None:
    readiness = _evaluate(_component("live"), lineage=_lineage(**lineage_changes))

    assert readiness.state == "stale"
    assert readiness.reason == expected_reason
    assert not readiness.usable


def test_current_consent_mismatch_invalidates_live_use_without_changing_the_artifact() -> None:
    component = _component("live")

    readiness = _evaluate(
        component,
        lineage=_lineage(),
        current_consent_version="stage-5-contribution-v2",
    )

    assert readiness.reason == "privacy_invalid"
    assert component.load_state == "loaded"
    assert component.artifact is not None


def test_invalid_clock_and_malformed_lineage_are_bounded_failures() -> None:
    naive_clock = _evaluate(
        _component("live"),
        lineage=_lineage(),
        now=NOW.replace(tzinfo=None),
    )
    malformed_lineage = _evaluate(
        _component("live"),
        lineage=_lineage(source_kind="fixture"),
    )

    assert naive_clock.reason == "artifact_incompatible"
    assert malformed_lineage.reason == "privacy_invalid"


def test_inconsistent_readiness_contracts_are_rejected() -> None:
    artifact = _fake_artifact("live")

    with pytest.raises(ValueError, match="state is inconsistent"):
        CollaborativeReadiness(
            state="fixture_only",
            reason=None,
            source_kind="live",
            artifact=artifact,
        )
    with pytest.raises(ValueError, match="state is inconsistent"):
        CollaborativeReadiness(
            state="future_state",  # type: ignore[arg-type]
            reason="artifact_stale",
            source_kind="live",
            artifact=None,
        )
    with pytest.raises(ValueError, match="state is inconsistent"):
        CollaborativeReadiness(
            state="stale",
            reason="future_reason",  # type: ignore[arg-type]
            source_kind="live",
            artifact=None,
        )
