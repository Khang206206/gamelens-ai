import hashlib
import json
import math
from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

from gamelens_recommender import (
    ArtifactError,
    BaseCandidateScore,
    CatalogItem,
    ContentRanker,
    UserContext,
    build_artifact,
    canonical_snapshot,
    load_artifact,
)
from gamelens_recommender import ranking as ranking_module
from gamelens_recommender.baseline import popularity_baseline
from gamelens_recommender.config import POPULARITY_CONFIG, RANKING_CONFIG
from gamelens_recommender.features import build_content_document, fit_features
from gamelens_recommender.ranking import BaseCandidateMaterializationError


def _replace_artifact_member(root: Path, name: str, value: bytes) -> None:
    (root / name).write_bytes(value)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["members"][name] = {
        "size": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _replace_numeric_member(root: Path, name: str, value: np.ndarray) -> None:
    stream = BytesIO()
    np.save(stream, value, allow_pickle=False)
    _replace_artifact_member(root, name, stream.getvalue())


def _first_row_with_entries(root: Path, minimum: int) -> tuple[int, int]:
    indptr = np.load(root / "matrix-indptr.npy", allow_pickle=False)
    for row in range(len(indptr) - 1):
        start = int(indptr[row])
        end = int(indptr[row + 1])
        if end - start >= minimum:
            return start, end
    raise AssertionError("Fixture artifact does not contain a suitable sparse row")


def test_snapshot_is_normalized_order_independent_and_sensitive(item_factory) -> None:
    first = item_factory("beta-game")
    second = item_factory("alpha-game")
    ordered = canonical_snapshot([first, second])
    reversed_snapshot = canonical_snapshot([second, first])
    changed = canonical_snapshot([first, item_factory("alpha-game", description="A changed story")])
    assert ordered.fingerprint == reversed_snapshot.fingerprint
    assert [item.slug for item in ordered.items] == ["alpha-game", "beta-game"]
    assert changed.fingerprint != ordered.fingerprint


def test_snapshot_rejects_duplicates_and_non_finite(item_factory) -> None:
    duplicate = item_factory("same-game")
    with pytest.raises(ValueError, match="duplicate"):
        canonical_snapshot([duplicate, duplicate])
    invalid = CatalogItem(**{**item_factory("invalid-game").__dict__, "popularity_score": math.inf})
    with pytest.raises(ValueError, match="finite"):
        canonical_snapshot([invalid])


def test_features_are_sparse_and_platform_is_separate(item_factory, snapshot) -> None:
    item = item_factory(
        "platform-game",
        title="Café Racer",
        platforms=("rare-platform",),
    ).canonical()
    document = build_content_document(item)
    vectorizer, matrix = fit_features(snapshot.items)
    assert "genre_strategy" in document
    assert "cafe racer" in document
    assert "caf racer" not in document
    assert "rare_platform" not in document
    assert matrix.shape[0] == len(snapshot.items)
    assert matrix.nnz < matrix.shape[0] * matrix.shape[1]
    assert matrix.has_canonical_format
    assert "genre_strategy" in vectorizer.vocabulary_


def test_popularity_prior_protects_rating_volume(item_factory) -> None:
    items = (
        item_factory("one-vote", rating=10, rating_count=1, popularity=0).canonical(),
        item_factory("supported", rating=9, rating_count=500, popularity=100).canonical(),
        item_factory("middle", rating=7, rating_count=100, popularity=50).canonical(),
    )
    scores = popularity_baseline(items)
    assert scores[1] > scores[0]
    assert np.all((scores >= 0) & (scores <= 1))


def test_model_owned_weight_and_policy_configuration_is_validated(item_factory) -> None:
    items = (item_factory("configured-game").canonical(),)
    invalid_popularity = replace(
        POPULARITY_CONFIG,
        rating_weight_units=-1,
        signal_weight_units=1_000_001,
    )
    invalid_ranking = replace(
        RANKING_CONFIG,
        content_weight_units=-1,
        platform_weight_units=900_001,
    )

    with pytest.raises(ValueError, match="non-negative"):
        popularity_baseline(items, invalid_popularity)
    with pytest.raises(ValueError, match="non-negative"):
        invalid_ranking.validate()
    with pytest.raises(ValueError, match="tie-break"):
        replace(RANKING_CONFIG, tie_break=("slug_asc",)).validate()


def test_artifact_round_trip_repeated_build_and_corruption(snapshot, tmp_path) -> None:
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    first = build_artifact(snapshot, tmp_path / "first", built_at=clock)
    shuffled = replace(snapshot, items=tuple(reversed(snapshot.items)))
    second = build_artifact(shuffled, tmp_path / "second", built_at=clock)
    artifact = load_artifact(first)
    assert artifact.data_fingerprint == snapshot.fingerprint
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }
    second_manifest_path = second / "manifest.json"
    second_manifest = json.loads(second_manifest_path.read_text(encoding="utf-8"))
    vectorizer_config = json.loads((second / "vectorizer-config.json").read_text(encoding="utf-8"))
    assert second_manifest["feature_config"]["strip_accents"] == "unicode"
    assert vectorizer_config["strip_accents"] == "unicode"
    second_manifest["ranking_config"]["content_weight_units"] = 799_999
    second_manifest_path.write_text(json.dumps(second_manifest), encoding="utf-8")
    with pytest.raises(ArtifactError, match="configuration is incompatible"):
        load_artifact(second)
    (first / "vocabulary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ArtifactError, match="size mismatch"):
        load_artifact(first)


def test_artifact_build_rejects_incorrect_snapshot_fingerprint(snapshot, tmp_path) -> None:
    invalid = replace(snapshot, fingerprint="0" * 64)

    with pytest.raises(ValueError, match="fingerprint"):
        build_artifact(invalid, tmp_path / "model")


def test_artifact_loader_rejects_shuffled_catalog_rows(snapshot, tmp_path) -> None:
    root = build_artifact(snapshot, tmp_path / "model")
    items_path = root / "catalog-items.json"
    items = list(reversed(json.loads(items_path.read_text(encoding="utf-8"))))
    _replace_artifact_member(root, "catalog-items.json", json.dumps(items).encode("utf-8"))
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["row_slugs"] = [item["slug"] for item in items]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ArtifactError) as caught:
        load_artifact(root)

    assert caught.value.code == "artifact_integrity_failed"


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        pytest.param("title", None, id="null-title"),
        pytest.param("description", "   ", id="blank-description"),
        pytest.param("rating_count", True, id="boolean-rating-count"),
        pytest.param("rating_count", 1.5, id="fractional-rating-count"),
        pytest.param("genre_slug", True, id="boolean-taxonomy-slug"),
    ],
)
def test_artifact_loader_rejects_invalid_catalog_json_types(
    snapshot,
    tmp_path,
    field,
    invalid,
) -> None:
    root = build_artifact(snapshot, tmp_path / "model")
    items_path = root / "catalog-items.json"
    items = json.loads(items_path.read_text(encoding="utf-8"))
    if field == "genre_slug":
        items[0]["genres"][0]["slug"] = invalid
    else:
        items[0][field] = invalid
    _replace_artifact_member(root, "catalog-items.json", json.dumps(items).encode("utf-8"))

    with pytest.raises(ArtifactError) as caught:
        load_artifact(root)

    assert caught.value.code == "manifest_invalid"


@pytest.mark.parametrize("corruption", ["negative", "zero-row", "unnormalized"])
def test_artifact_loader_rejects_invalid_feature_values(
    snapshot,
    tmp_path,
    corruption,
) -> None:
    root = build_artifact(snapshot, tmp_path / "model")
    data = np.load(root / "matrix-data.npy", allow_pickle=False).copy()
    start, end = _first_row_with_entries(root, minimum=1)
    if corruption == "negative":
        data[start] = -abs(data[start])
    elif corruption == "zero-row":
        data[start:end] = 0
    else:
        data[start:end] *= 2
    _replace_numeric_member(root, "matrix-data.npy", data)

    with pytest.raises(ArtifactError) as caught:
        load_artifact(root)

    assert caught.value.code == "artifact_numeric_invalid"


@pytest.mark.parametrize("corruption", ["unsorted", "duplicate"])
def test_artifact_loader_rejects_noncanonical_sparse_indices(
    snapshot,
    tmp_path,
    corruption,
) -> None:
    root = build_artifact(snapshot, tmp_path / "model")
    indices = np.load(root / "matrix-indices.npy", allow_pickle=False).copy()
    start, _ = _first_row_with_entries(root, minimum=2)
    if corruption == "unsorted":
        indices[[start, start + 1]] = indices[[start + 1, start]]
    else:
        indices[start + 1] = indices[start]
    _replace_numeric_member(root, "matrix-indices.npy", indices)

    with pytest.raises(ArtifactError) as caught:
        load_artifact(root)

    assert caught.value.code == "artifact_format_invalid"


def test_artifact_rejects_checksum_valid_empty_numeric_member(snapshot, tmp_path) -> None:
    root = build_artifact(snapshot, tmp_path / "model")
    _replace_artifact_member(root, "matrix-data.npy", b"")

    with pytest.raises(ArtifactError) as caught:
        load_artifact(root)

    assert caught.value.code == "artifact_numeric_invalid"

    idf_root = build_artifact(snapshot, tmp_path / "invalid-idf")
    idf = np.load(idf_root / "inverse-document-frequency.npy", allow_pickle=False).copy()
    idf[0] = 0.5
    _replace_numeric_member(idf_root, "inverse-document-frequency.npy", idf)

    with pytest.raises(ArtifactError) as caught:
        load_artifact(idf_root)

    assert caught.value.code == "artifact_numeric_invalid"

    oversized_root = build_artifact(snapshot, tmp_path / "oversized-number")
    items_path = oversized_root / "catalog-items.json"
    items = json.loads(items_path.read_text(encoding="utf-8"))
    items[0]["popularity_score"] = 10**400
    _replace_artifact_member(
        oversized_root,
        "catalog-items.json",
        json.dumps(items).encode("utf-8"),
    )

    with pytest.raises(ArtifactError) as caught:
        load_artifact(oversized_root)

    assert caught.value.code == "manifest_invalid"


def test_artifact_rejects_manifest_vocabulary_size_mismatch(snapshot, tmp_path) -> None:
    root = build_artifact(snapshot, tmp_path / "model")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["vocabulary_size"] += 1
    manifest["matrix"]["shape"][1] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ArtifactError) as caught:
        load_artifact(root)

    assert caught.value.code == "artifact_shape_invalid"


def test_loaded_artifact_runtime_state_is_immutable(snapshot, tmp_path) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))

    with pytest.raises(TypeError):
        artifact.slug_to_row["new-game"] = 0
    with pytest.raises(TypeError):
        artifact.manifest["data_fingerprint"] = "changed"
    with pytest.raises(TypeError):
        artifact.vectorizer.vocabulary_["new_token"] = len(artifact.vectorizer.vocabulary_)
    with pytest.raises(ValueError):
        artifact.vectorizer.idf_[0] = 0
    with pytest.raises(ValueError):
        artifact.matrix.data[0] = 0


def test_ranking_is_deterministic_excludes_selected_and_reconstructs_score(
    snapshot, tmp_path
) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    ranker = ContentRanker(artifact)
    context = UserContext(
        selected_game_slugs=("alpha-tactics",),
        preferred_genres=("strategy",),
        preferred_platforms=("linux",),
        top_k=3,
    )
    first = ranker.rank(context)
    assert first == ranker.rank(context)
    assert first.items
    assert all(item.slug != "alpha-tactics" for item in first.items)
    assert [item.rank for item in first.items] == list(range(1, len(first.items) + 1))
    assert all(
        sum(component.contribution_units for component in item.components) == item.final_score_units
        for item in first.items
    )


def test_pre_truncation_scoring_preserves_stage_3_golden_contract(snapshot, tmp_path) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    ranker = ContentRanker(artifact)
    context = UserContext(
        selected_game_slugs=("alpha-tactics",),
        preferred_genres=("strategy",),
        preferred_platforms=("linux",),
        top_k=3,
    )

    candidates = ranker.score_candidates(context)
    result = ranker.rank(context)

    assert [
        (
            value.slug,
            value.base_score_units,
            value.content_score_units,
            value.platform_score_units,
            value.popularity_score_units,
        )
        for value in candidates
    ] == [
        ("delta-command", 489_035, 420_044, 1_000_000, 530_000),
        ("beta-kingdom", 467_586, 378_233, 1_000_000, 650_000),
        ("gamma-drift", 59_534, 30_668, 0, 350_000),
    ]
    assert [
        (
            value.slug,
            value.final_score_units,
            tuple(
                (
                    component.name,
                    component.raw_units,
                    component.weight_units,
                    component.contribution_units,
                )
                for component in value.components
            ),
        )
        for value in result.items
    ] == [
        (
            "delta-command",
            489_035,
            (
                ("content", 420_044, 800_000, 336_035),
                ("platform", 1_000_000, 100_000, 100_000),
                ("popularity", 530_000, 100_000, 53_000),
            ),
        ),
        (
            "beta-kingdom",
            467_586,
            (
                ("content", 378_233, 800_000, 302_586),
                ("platform", 1_000_000, 100_000, 100_000),
                ("popularity", 650_000, 100_000, 65_000),
            ),
        ),
        (
            "gamma-drift",
            59_534,
            (
                ("content", 30_668, 800_000, 24_534),
                ("platform", 0, 100_000, 0),
                ("popularity", 350_000, 100_000, 35_000),
            ),
        ),
    ]
    assert result.reason == "recommendations"
    assert [
        (
            value.slug,
            value.rank,
            tuple((item.slug, item.name) for item in value.evidence.matching_genres),
            tuple((item.slug, item.name) for item in value.evidence.matching_tags),
            tuple((item.slug, item.name) for item in value.evidence.preferred_platforms),
            tuple(
                (item.slug, item.title, item.similarity_units)
                for item in value.evidence.similar_selected_games
            ),
            value.evidence.popularity_percentile_units,
            value.explanation_summary,
            value.explanation_reasons,
        )
        for value in result.items
    ] == [
        (
            "delta-command",
            1,
            (("strategy", "Strategy"),),
            (),
            (("linux", "LINUX"),),
            (("alpha-tactics", "Alpha Tactics", 389_497),),
            530_000,
            "Its content profile is similar to Alpha Tactics.",
            (
                "Its content profile is similar to Alpha Tactics.",
                "It matches your preferred genres: Strategy.",
                "It is available on preferred platforms: LINUX.",
            ),
        ),
        (
            "beta-kingdom",
            2,
            (("strategy", "Strategy"),),
            (),
            (("linux", "LINUX"),),
            (("alpha-tactics", "Alpha Tactics", 341_166),),
            650_000,
            "Its content profile is similar to Alpha Tactics.",
            (
                "Its content profile is similar to Alpha Tactics.",
                "It matches your preferred genres: Strategy.",
                "It is available on preferred platforms: LINUX.",
            ),
        ),
        (
            "gamma-drift",
            3,
            (),
            (),
            (),
            (("alpha-tactics", "Alpha Tactics", 38_481),),
            350_000,
            "Its content profile is similar to Alpha Tactics.",
            ("Its content profile is similar to Alpha Tactics.",),
        ),
    ]


def test_exact_base_materialization_matches_full_catalog_components(snapshot, tmp_path) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    ranker = ContentRanker(artifact)
    context = UserContext(
        selected_game_slugs=("alpha-tactics",),
        preferred_genres=("strategy",),
        preferred_platforms=("linux",),
    )
    full_catalog = ranker.score_candidates(context)
    requested = tuple(reversed(tuple(candidate.slug for candidate in full_catalog)))

    exact = ranker.materialize_base_candidates(context, requested)

    assert exact == tuple(sorted(full_catalog, key=lambda candidate: candidate.slug))


def test_exact_base_materialization_keeps_zero_content_and_selected_rows(
    snapshot,
    tmp_path,
) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    ranker = ContentRanker(artifact)
    zero_content_context = UserContext(
        preferred_genres=("strategy",),
        preferred_platforms=("console",),
    )

    assert all(
        candidate.slug != "gamma-drift"
        for candidate in ranker.score_candidates(zero_content_context)
    )
    assert ranker.materialize_base_candidates(
        zero_content_context,
        ("gamma-drift",),
    ) == (
        BaseCandidateScore(
            slug="gamma-drift",
            base_score_units=135_000,
            content_score_units=0,
            platform_score_units=1_000_000,
            popularity_score_units=350_000,
        ),
    )

    selected_context = UserContext(selected_game_slugs=("alpha-tactics",))
    assert all(
        candidate.slug != "alpha-tactics" for candidate in ranker.score_candidates(selected_context)
    )
    selected = ranker.materialize_base_candidates(selected_context, ("alpha-tactics",))
    assert selected[0].slug == "alpha-tactics"
    assert selected[0].content_score_units == 1_000_000


def test_exact_base_materialization_reads_only_canonical_requested_rows(
    snapshot,
    tmp_path,
) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    matrix = artifact.matrix
    row_reads: list[tuple[int, ...]] = []

    class RecordingMatrix:
        shape = matrix.shape

        def __getitem__(self, rows):
            row_reads.append(tuple(int(row) for row in rows))
            return matrix[rows]

    ranker = ContentRanker(replace(artifact, matrix=RecordingMatrix()))
    context = UserContext(preferred_genres=("strategy",))
    first = ranker.materialize_base_candidates(
        context,
        ("gamma-drift", "beta-kingdom"),
    )
    second = ranker.materialize_base_candidates(
        context,
        ("beta-kingdom", "gamma-drift"),
    )

    expected_rows = (
        artifact.slug_to_row["beta-kingdom"],
        artifact.slug_to_row["gamma-drift"],
    )
    assert first == second
    assert tuple(candidate.slug for candidate in first) == (
        "beta-kingdom",
        "gamma-drift",
    )
    assert {candidate.content_score_units for candidate in first} == {0, 247_788}
    assert row_reads == [expected_rows, expected_rows]


def test_exact_base_materialization_accepts_empty_candidate_set(snapshot, tmp_path) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    ranker = ContentRanker(artifact)

    assert (
        ranker.materialize_base_candidates(
            UserContext(preferred_genres=("strategy",)),
            (),
        )
        == ()
    )


@pytest.mark.parametrize(
    ("candidate_slugs", "expected_code"),
    [
        pytest.param(
            ["beta-kingdom"],
            "materialization_input_invalid",
            id="mutable-container",
        ),
        pytest.param(
            ("beta-kingdom", "beta-kingdom"),
            "materialization_input_invalid",
            id="duplicate",
        ),
        pytest.param(
            ("Beta-Kingdom",),
            "materialization_input_invalid",
            id="noncanonical",
        ),
        pytest.param(
            ("unknown-game",),
            "materialization_artifact_incompatible",
            id="missing",
        ),
        pytest.param(
            tuple(f"unknown-{index}" for index in range(1_000)),
            "materialization_artifact_incompatible",
            id="at-cap",
        ),
        pytest.param(
            tuple(f"unknown-{index}" for index in range(1_001)),
            "materialization_input_invalid",
            id="over-cap",
        ),
    ],
)
def test_exact_base_materialization_rejects_invalid_or_incompatible_slugs(
    snapshot,
    tmp_path,
    monkeypatch,
    candidate_slugs,
    expected_code,
) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    ranker = ContentRanker(artifact)

    def unexpected_context_traversal(_context):
        raise AssertionError("Invalid exact candidates must fail before context traversal")

    monkeypatch.setattr(ranker, "_validated_user_vector", unexpected_context_traversal)
    with pytest.raises(BaseCandidateMaterializationError) as captured:
        ranker.materialize_base_candidates(
            UserContext(preferred_genres=("strategy",)),
            candidate_slugs,
        )

    assert captured.value.code == expected_code


def test_taxonomy_preference_order_does_not_change_ranking(snapshot, tmp_path) -> None:
    ranker = ContentRanker(load_artifact(build_artifact(snapshot, tmp_path / "model")))
    first = ranker.rank(
        UserContext(
            preferred_genres=("strategy", "racing"),
            preferred_tags=("tactical", "arcade"),
        )
    )
    reordered = ranker.rank(
        UserContext(
            preferred_genres=("racing", "strategy"),
            preferred_tags=("arcade", "tactical"),
        )
    )

    assert first == reordered


def test_platform_only_context_is_rejected(snapshot, tmp_path) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    with pytest.raises(ValueError, match="At least one"):
        ContentRanker(artifact).rank(UserContext(preferred_platforms=("linux",)))


def test_ranking_materializes_evidence_only_for_top_k(snapshot, tmp_path, monkeypatch) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    original_explain = ranking_module._explain
    calls = 0

    def counted_explain(evidence):
        nonlocal calls
        calls += 1
        return original_explain(evidence)

    monkeypatch.setattr(ranking_module, "_explain", counted_explain)
    result = ContentRanker(artifact).rank(UserContext(preferred_genres=("strategy",), top_k=1))

    assert len(result.items) == 1
    assert calls == 1
