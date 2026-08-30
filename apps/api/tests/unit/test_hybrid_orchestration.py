from dataclasses import replace
from datetime import UTC, datetime

import pytest
from app.commands.collaborative_artifact import build_fixture_artifact
from app.commands.collaborative_snapshot import catalog_from_seed
from app.core.config import PROJECT_ROOT, Settings
from app.core.exceptions import RecommendationUnavailableError
from app.services.recommendation import (
    COLLABORATIVE_READINESS_REASONS,
    CollaborativeReadiness,
    LifecycleAwareHybridOrchestrator,
    create_collaborative_component,
    evaluate_collaborative_readiness,
)
from app.services.recommendation.content import ContentRecommendationService
from gamelens_recommender import (
    COLLABORATIVE_NO_SUPPORT_REASONS,
    ActiveGameFeedback,
    CollaborativeScoringDiagnostics,
    CollaborativeScoringResult,
    HybridRecommendationsResult,
    LoadedCollaborativeArtifact,
    Stage4FallbackResult,
    UserContext,
    build_artifact,
    load_artifact,
)
from gamelens_recommender.collaborative import COLLABORATIVE_SCORING_CONFIG

CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "games.json"
FIXTURE_PATH = (
    PROJECT_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)
BUILT_AT = datetime(2026, 8, 25, tzinfo=UTC)
FEEDBACK_AT = datetime(2026, 8, 24, tzinfo=UTC)


class _StaticScorer:
    def __init__(self, result: CollaborativeScoringResult) -> None:
        self.result = result

    def score(self, context):  # type: ignore[no-untyped-def]
        assert context.sources == self.result.query_sources
        return self.result


class _FailingScorer:
    def score(self, _context):  # type: ignore[no-untyped-def]
        raise RuntimeError("private scorer failure detail")


class _ScorerFactory:
    def __init__(self, scorer: object) -> None:
        self.scorer = scorer
        self.artifacts: list[LoadedCollaborativeArtifact] = []

    def __call__(self, artifact: LoadedCollaborativeArtifact):  # type: ignore[no-untyped-def]
        self.artifacts.append(artifact)
        return self.scorer


@pytest.fixture(scope="module")
def orchestration_fixture(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("hybrid-orchestration")
    snapshot = catalog_from_seed(CATALOG_PATH)
    content_root = build_artifact(snapshot, root / "content", built_at=BUILT_AT)
    content = ContentRecommendationService(load_artifact(content_root))
    collaborative_root = root / "collaborative"
    settings = Settings(
        _env_file=None,
        environment="test",
        collaborative_allow_test_fixture=True,
    )
    build_fixture_artifact(
        settings,
        collaborative_root,
        fixture_path=FIXTURE_PATH,
        catalog_path=CATALOG_PATH,
        built_at=BUILT_AT,
    )
    component = create_collaborative_component(
        collaborative_root,
        environment="test",
        allow_test_fixture=True,
    )
    readiness = evaluate_collaborative_readiness(
        component,
        catalog_fingerprint=snapshot.fingerprint,
        current_consent_version=None,
        now=BUILT_AT,
    )
    assert readiness.state == "fixture_only"
    return snapshot, content, readiness


def _liked(slug: str) -> tuple[ActiveGameFeedback, ...]:
    return (
        ActiveGameFeedback(
            game_slug=slug,
            reaction="liked",
            reaction_occurred_at=FEEDBACK_AT,
        ),
    )


def _phase4_signature(result: HybridRecommendationsResult):
    return tuple(
        (
            item.slug,
            item.rank,
            item.candidate_origin,
            item.base_score_units,
            tuple(component.raw_units for component in item.base_components),
            item.affinity_score_units,
            item.collaborative_score_units,
            item.base_contribution_units,
            item.affinity_contribution_units,
            item.collaborative_contribution_units,
            item.pre_played_score_units,
            item.played_factor_units,
            item.played_delta_units,
            item.final_score_units,
        )
        for item in result.items
    )


def _unavailable_readiness(reason: str) -> CollaborativeReadiness:
    if reason == "not_configured":
        state = "not_configured"
        source_kind = None
    elif reason == "insufficient_data":
        state = "insufficient_data"
        source_kind = "fixture"
    elif reason in {"fixture_not_allowed", "artifact_missing", "artifact_corrupt"}:
        state = "unavailable"
        source_kind = None
    else:
        state = "stale"
        source_kind = "live"
    return CollaborativeReadiness(
        state=state,  # type: ignore[arg-type]
        reason=reason,  # type: ignore[arg-type]
        source_kind=source_kind,  # type: ignore[arg-type]
        artifact=None,
    )


def _no_support_result(prepared, reason: str) -> CollaborativeScoringResult:
    query_sources = prepared.collaborative_query_context.sources
    if reason == "no_query_sources":
        supported: tuple[str, ...] = ()
        unsupported: tuple[str, ...] = ()
        diagnostics = CollaborativeScoringDiagnostics(0, 0, 0, 0, 0, 0, 0, 0, 0)
    elif reason == "no_supported_sources":
        supported = ()
        unsupported = tuple(source.game_slug for source in query_sources)
        diagnostics = CollaborativeScoringDiagnostics(
            len(query_sources), 0, len(query_sources), 0, 0, 0, 0, 0, 0
        )
    elif reason == "no_candidate_edges":
        supported = (query_sources[0].game_slug,)
        unsupported = tuple(source.game_slug for source in query_sources[1:])
        diagnostics = CollaborativeScoringDiagnostics(
            len(query_sources), 1, len(query_sources) - 1, 1, 0, 0, 0, 0, 0
        )
    else:
        assert reason == "no_eligible_candidates"
        supported = (query_sources[0].game_slug,)
        unsupported = tuple(source.game_slug for source in query_sources[1:])
        diagnostics = CollaborativeScoringDiagnostics(
            len(query_sources), 1, len(query_sources) - 1, 0, 1, 1, 1, 0, 0
        )
    result = CollaborativeScoringResult(
        reason=reason,  # type: ignore[arg-type]
        identity=COLLABORATIVE_SCORING_CONFIG.identity,
        query_sources=query_sources,
        supported_source_slugs=supported,
        unsupported_source_slugs=unsupported,
        candidates=(),
        diagnostics=diagnostics,
    )
    result.validate()
    return result


def _assert_exact_stage4_fallback(
    result,
    expected,
    *,
    reason: str,
    returned: list,
) -> None:
    assert type(result) is Stage4FallbackResult
    assert result.mode == "stage_4_fallback"
    assert result.fallback_reason == reason
    assert len(returned) == 1
    assert result.stage_4_result is returned[0]
    assert result.stage_4_result == expected
    assert repr(result.stage_4_result).encode() == repr(expected).encode()


def test_guarded_fixture_matches_the_frozen_phase4_hybrid_golden(
    orchestration_fixture,
) -> None:
    snapshot, content, readiness = orchestration_fixture
    context = UserContext(
        preferred_genres=("strategy",),
        preferred_platforms=("windows",),
        top_k=20,
    )
    feedback = _liked("emberfall-tactics")
    orchestrator = LifecycleAwareHybridOrchestrator(content)

    first = orchestrator.rank(
        snapshot=snapshot,
        context=context,
        feedback=feedback,
        collaborative_readiness=readiness,
    )
    second = orchestrator.rank(
        snapshot=snapshot,
        context=context,
        feedback=feedback,
        collaborative_readiness=readiness,
    )

    assert type(first) is HybridRecommendationsResult
    assert first == second
    assert _phase4_signature(first) == (
        (
            "warden-of-glass",
            1,
            "content",
            304_504,
            (164_937, 1_000_000, 725_539),
            311_593,
            0,
            243_603,
            31_159,
            0,
            274_762,
            1_000_000,
            0,
            274_762,
        ),
        (
            "paper-kingdoms",
            2,
            "content",
            301_576,
            (160_315, 1_000_000, 733_240),
            161_703,
            0,
            241_261,
            16_170,
            0,
            257_431,
            1_000_000,
            0,
            257_431,
        ),
        (
            "frontier-foundry",
            3,
            "content",
            314_452,
            (173_884, 1_000_000, 753_454),
            47_368,
            0,
            251_562,
            4_737,
            0,
            256_299,
            1_000_000,
            0,
            256_299,
        ),
        (
            "frostline-caravan",
            4,
            "content",
            299_820,
            (164_451, 1_000_000, 682_589),
            116_234,
            0,
            239_856,
            11_623,
            0,
            251_479,
            1_000_000,
            0,
            251_479,
        ),
        (
            "null-protocol",
            5,
            "content",
            305_852,
            (155_451, 1_000_000, 814_912),
            49_553,
            0,
            244_682,
            4_955,
            0,
            249_637,
            1_000_000,
            0,
            249_637,
        ),
        (
            "harborlight",
            6,
            "content",
            286_872,
            (182_485, 1_000_000, 408_836),
            58_170,
            0,
            229_498,
            5_817,
            0,
            235_315,
            1_000_000,
            0,
            235_315,
        ),
        (
            "tin-star-sheriff",
            7,
            "content",
            265_626,
            (154_211, 1_000_000, 422_569),
            191_465,
            0,
            212_501,
            19_147,
            0,
            231_648,
            1_000_000,
            0,
            231_648,
        ),
        (
            "verdant-vale",
            8,
            "collaborative",
            196_637,
            (0, 1_000_000, 966_366),
            0,
            428_571,
            157_310,
            0,
            42_857,
            200_167,
            1_000_000,
            0,
            200_167,
        ),
        (
            "neon-drift-circuit",
            9,
            "collaborative",
            155_118,
            (0, 1_000_000, 551_178),
            7_170,
            571_429,
            124_094,
            717,
            57_143,
            181_954,
            1_000_000,
            0,
            181_954,
        ),
        (
            "starbound-couriers",
            10,
            "collaborative",
            159_912,
            (0, 1_000_000, 599_117),
            0,
            428_571,
            127_930,
            0,
            42_857,
            170_787,
            1_000_000,
            0,
            170_787,
        ),
        (
            "clockwork-orchard",
            11,
            "collaborative",
            129_531,
            (0, 1_000_000, 295_311),
            0,
            462_910,
            103_625,
            0,
            46_291,
            149_916,
            1_000_000,
            0,
            149_916,
        ),
    )


@pytest.mark.parametrize("reason", COLLABORATIVE_READINESS_REASONS)
def test_every_lifecycle_unavailability_returns_exact_stage4_payload(
    orchestration_fixture,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    snapshot, content, _readiness = orchestration_fixture
    context = UserContext(preferred_genres=("strategy",), top_k=5)
    feedback = _liked("emberfall-tactics")
    original_rank = content.feedback_ranker.rank
    expected = original_rank(context, feedback)
    returned = []

    def tracked_rank(actual_context, actual_feedback):  # type: ignore[no-untyped-def]
        result = original_rank(actual_context, actual_feedback)
        returned.append(result)
        return result

    monkeypatch.setattr(content.feedback_ranker, "rank", tracked_rank)
    result = LifecycleAwareHybridOrchestrator(content).rank(
        snapshot=snapshot,
        context=context,
        feedback=feedback,
        collaborative_readiness=_unavailable_readiness(reason),
    )

    _assert_exact_stage4_fallback(result, expected, reason=reason, returned=returned)


@pytest.mark.parametrize("reason", COLLABORATIVE_NO_SUPPORT_REASONS)
def test_every_no_support_reason_returns_exact_stage4_payload(
    orchestration_fixture,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    snapshot, content, readiness = orchestration_fixture
    context = UserContext(preferred_genres=("strategy",), top_k=5)
    feedback = () if reason == "no_query_sources" else _liked("emberfall-tactics")
    prepared = content.feedback_ranker.prepare_ranking_context(context, feedback)
    scorer = _StaticScorer(_no_support_result(prepared, reason))
    factory = _ScorerFactory(scorer)
    original_rank = content.feedback_ranker.rank
    expected = original_rank(context, feedback)
    returned = []

    def tracked_rank(actual_context, actual_feedback):  # type: ignore[no-untyped-def]
        result = original_rank(actual_context, actual_feedback)
        returned.append(result)
        return result

    monkeypatch.setattr(content.feedback_ranker, "rank", tracked_rank)
    result = LifecycleAwareHybridOrchestrator(content, scorer_factory=factory).rank(
        snapshot=snapshot,
        context=context,
        feedback=feedback,
        collaborative_readiness=readiness,
    )

    _assert_exact_stage4_fallback(result, expected, reason=reason, returned=returned)
    assert factory.artifacts == [readiness.artifact]


def test_scorer_failure_isolated_as_artifact_incompatible_stage4_fallback(
    orchestration_fixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    snapshot, content, readiness = orchestration_fixture
    context = UserContext(preferred_genres=("strategy",), top_k=5)
    feedback = _liked("emberfall-tactics")
    original_rank = content.feedback_ranker.rank
    expected = original_rank(context, feedback)
    returned = []

    def tracked_rank(actual_context, actual_feedback):  # type: ignore[no-untyped-def]
        result = original_rank(actual_context, actual_feedback)
        returned.append(result)
        return result

    monkeypatch.setattr(content.feedback_ranker, "rank", tracked_rank)
    with caplog.at_level("WARNING"):
        result = LifecycleAwareHybridOrchestrator(
            content,
            scorer_factory=_ScorerFactory(_FailingScorer()),
        ).rank(
            snapshot=snapshot,
            context=context,
            feedback=feedback,
            collaborative_readiness=readiness,
        )

    _assert_exact_stage4_fallback(
        result,
        expected,
        reason="artifact_incompatible",
        returned=returned,
    )
    assert "private scorer failure detail" not in caplog.text
    assert caplog.records[-1].error_type == "RuntimeError"
    assert caplog.records[-1].fallback_reason == "artifact_incompatible"


def test_content_catalog_failure_keeps_existing_exception_semantics(
    orchestration_fixture,
) -> None:
    snapshot, content, readiness = orchestration_fixture
    stale_snapshot = replace(snapshot, fingerprint="0" * 64)
    factory = _ScorerFactory(_FailingScorer())

    with pytest.raises(RecommendationUnavailableError) as captured:
        LifecycleAwareHybridOrchestrator(content, scorer_factory=factory).rank(
            snapshot=stale_snapshot,
            context=UserContext(preferred_genres=("strategy",), top_k=5),
            feedback=_liked("emberfall-tactics"),
            collaborative_readiness=readiness,
        )

    assert captured.value.code == "catalog_stale"
    assert factory.artifacts == []
