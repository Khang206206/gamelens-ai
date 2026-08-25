import json
from pathlib import Path

import pytest

from gamelens_recommender.interaction_snapshot import (
    MAX_FIXTURE_BYTES,
    SnapshotAuditError,
    audit_fixture,
    audit_profiles,
    canonicalize_profiles,
    load_fixture,
    profile_fingerprint,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY_ROOT / "data" / "catalog" / "games.json"
FIXTURE_PATH = (
    REPOSITORY_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)
CATALOG_FINGERPRINT = "a" * 64


def _catalog_slugs() -> frozenset[str]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return frozenset(game["slug"] for game in payload["games"])


def test_project_authored_fixture_is_deterministic_and_aggregate_only() -> None:
    report = audit_fixture(
        FIXTURE_PATH,
        catalog_slugs=_catalog_slugs(),
        catalog_fingerprint=CATALOG_FINGERPRINT,
    )

    assert report["ready_for_functional_build"] is True
    assert report["candidate_profiles"] == {
        "contributors": 12,
        "positive_edges": 36,
        "distinct_items": 6,
        "profile_size_distribution": {
            "0": 0,
            "1": 0,
            "2": 0,
            "3-4": 12,
            "5-9": 0,
            "10+": 0,
        },
    }
    assert (
        report["interaction_fingerprint"]
        == "d2ec587ef4e06eeaaf918447e58d8c233840575a33299556eb9765b786a1c003"
    )
    assert (
        report["fixture"]["contract_fingerprint"]
        == "ef19493c08a5f60b1ef868ad1b586581679ca13fa680e896d0a658bcbe9fae05"
    )
    assert report["fixture"]["fixture_id"] == "stage-5-collaborative-interactions-v1"
    assert report["fixture"]["cold_start_unsupported_item"] == "abyssal-signal"
    assert report["exclusion_counts"] == {
        "disliked": 1,
        "low_rating": 1,
        "played_only": 1,
        "unknown_game": 1,
        "viewed_only": 1,
        "wishlisted_only": 1,
    }
    assert report["pair_support"]["pair_contributions"] == 36
    assert report["pair_support"]["distinct_pairs"] == 14
    assert report["pair_support"]["supported_pairs"] == 10
    assert report["privacy"] == {
        "aggregate_only": True,
        "user_identifiers_emitted": False,
        "row_level_snapshot_written": False,
        "cohort_mapping_written": False,
    }
    serialized = json.dumps(report, sort_keys=True)
    assert "synthetic-01" not in serialized
    assert '"user_id":' not in serialized


def test_profile_fingerprint_is_order_and_identity_invariant() -> None:
    catalog = frozenset({"alpha", "beta", "gamma"})
    first = canonicalize_profiles(
        (("gamma", "alpha"), ("beta", "alpha"), ("alpha", "gamma")),
        catalog_slugs=catalog,
    )
    second = canonicalize_profiles(
        (("gamma", "alpha"), ("alpha", "gamma"), ("alpha", "beta")),
        catalog_slugs=catalog,
    )

    assert first == second
    assert profile_fingerprint(first) == profile_fingerprint(second)


def test_empty_snapshot_returns_typed_insufficiency_reasons() -> None:
    report = audit_profiles(
        (),
        source_kind="live",
        catalog_fingerprint=CATALOG_FINGERPRINT,
    )

    assert report["status"] == "insufficient_data"
    assert report["reasons"] == [
        "no_contributors",
        "no_multi_positive_users",
        "unsupported_items",
        "no_supported_pairs",
        "insufficient_activation_users",
        "insufficient_activation_edges",
        "insufficient_activation_items",
    ]
    assert report["approved_live_training_eligibility"] is False


def test_fixture_rejects_unknown_catalog_slug() -> None:
    with pytest.raises(SnapshotAuditError, match="unknown game slug") as error:
        load_fixture(FIXTURE_PATH, catalog_slugs=frozenset({"abyssal-signal"}))

    assert error.value.code == "catalog_mismatch"


def test_fixture_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"fixture_schema_version":1,"fixture_schema_version":1}', encoding="utf-8")

    with pytest.raises(SnapshotAuditError, match="Duplicate fixture key") as error:
        load_fixture(path, catalog_slugs=frozenset())

    assert error.value.code == "fixture_invalid"


def test_fixture_read_is_bounded_before_json_parsing(tmp_path: Path) -> None:
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * (MAX_FIXTURE_BYTES + 1))

    with pytest.raises(SnapshotAuditError, match="maximum byte size") as error:
        load_fixture(path, catalog_slugs=_catalog_slugs())

    assert error.value.code == "fixture_limit_exceeded"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"raw_user_rows": []}),
        lambda payload: payload["profiles"][0].update({"user_id": 123}),
        lambda payload: payload["profiles"][0]["excluded"][0].update({"raw_feedback": "hidden"}),
        lambda payload: payload["cold_start"].update({"profile_mapping": {}}),
    ],
)
def test_fixture_rejects_unrecognized_identity_or_raw_fields(
    tmp_path: Path,
    mutate,  # type: ignore[no-untyped-def]
) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    mutate(payload)
    path = tmp_path / "extra-fields.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotAuditError, match="keys are invalid") as error:
        load_fixture(path, catalog_slugs=_catalog_slugs())

    assert error.value.code == "fixture_invalid"


@pytest.mark.parametrize("contract_part", ["labels", "exclusions"])
def test_fixture_exact_label_and_exclusion_contract_rejects_drift(
    tmp_path: Path,
    contract_part: str,
) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if contract_part == "labels":
        positives = payload["profiles"][0]["positive_game_slugs"]
        positives[2] = "starbound-couriers"
        payload["profiles"][0]["positive_game_slugs"] = sorted(positives)
    else:
        first_reason = payload["profiles"][0]["excluded"][0]["reason"]
        third_reason = payload["profiles"][2]["excluded"][0]["reason"]
        payload["profiles"][0]["excluded"][0]["reason"] = third_reason
        payload["profiles"][2]["excluded"][0]["reason"] = first_reason
    path = tmp_path / f"drifted-{contract_part}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotAuditError, match="audit drifted") as error:
        audit_fixture(
            path,
            catalog_slugs=_catalog_slugs(),
            catalog_fingerprint=CATALOG_FINGERPRINT,
        )
    assert error.value.code == "fixture_expectation_mismatch"


def test_fixture_schema_version_rejects_boolean_alias_for_one(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["fixture_schema_version"] = True
    path = tmp_path / "boolean-schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotAuditError, match="schema version") as error:
        load_fixture(path, catalog_slugs=_catalog_slugs())

    assert error.value.code == "fixture_invalid"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ready_for_functional_build", 1),
        ("candidate_profiles", 12.0),
    ],
)
def test_fixture_expected_audit_rejects_equal_but_different_json_types(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["expected_audit"][field] = value
    path = tmp_path / f"wrong-type-{field}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotAuditError, match="audit drifted") as error:
        audit_fixture(
            path,
            catalog_slugs=_catalog_slugs(),
            catalog_fingerprint=CATALOG_FINGERPRINT,
        )

    assert error.value.code == "fixture_expectation_mismatch"


def test_fixture_rejects_non_finite_json_constant(tmp_path: Path) -> None:
    payload = FIXTURE_PATH.read_text(encoding="utf-8").replace(
        '"candidate_profiles": 12',
        '"candidate_profiles": NaN',
    )
    path = tmp_path / "non-finite.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(SnapshotAuditError, match="non-finite") as error:
        load_fixture(path, catalog_slugs=_catalog_slugs())

    assert error.value.code == "fixture_invalid"


def test_fixture_expectation_and_provenance_drift_fail_closed(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["expected_audit"]["candidate_positive_edges"] = 999
    path = tmp_path / "drifted.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SnapshotAuditError, match="audit drifted") as error:
        audit_fixture(
            path,
            catalog_slugs=_catalog_slugs(),
            catalog_fingerprint=CATALOG_FINGERPRINT,
        )
    assert error.value.code == "fixture_expectation_mismatch"

    payload["expected_audit"]["candidate_positive_edges"] = 36
    payload["provenance"]["quality_evidence"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SnapshotAuditError, match="project-authored") as error:
        load_fixture(path, catalog_slugs=_catalog_slugs())
    assert error.value.code == "fixture_invalid"


def test_fixture_unknown_game_exclusion_must_be_outside_catalog(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    unknown_exclusion = payload["profiles"][5]["excluded"][0]
    assert unknown_exclusion["reason"] == "unknown_game"
    unknown_exclusion["game_slug"] = "abyssal-signal"
    path = tmp_path / "catalog-known-unknown.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotAuditError, match="outside the catalog") as error:
        load_fixture(path, catalog_slugs=_catalog_slugs())

    assert error.value.code == "fixture_invalid"
