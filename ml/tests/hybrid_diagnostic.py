"""Small synthetic five-variant diagnostic; no product policy or quality evaluation.

Run this file directly to print the retained Markdown table. All builds are
explicit fixture builds in a temporary directory, with no database access.
"""

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from gamelens_recommender import (
    ActiveGameFeedback,
    CatalogItem,
    CollaborativeBuildMetadata,
    CollaborativeComponentReady,
    CollaborativeScorer,
    FeedbackRanker,
    HybridRanker,
    Stage4FallbackResult,
    TaxonomyValue,
    UserContext,
    build_artifact,
    build_collaborative_artifact,
    canonical_snapshot,
    fit_collaborative_neighborhoods,
    load_artifact,
    load_collaborative_artifact,
)
from gamelens_recommender.baseline import popularity_baseline
from gamelens_recommender.config import POPULARITY_CONFIG, RANKING_CONFIG
from gamelens_recommender.interaction_snapshot import canonicalize_profiles, profile_fingerprint
from gamelens_recommender.ranking import quantize

BUILT_AT = datetime(2026, 9, 10, tzinfo=UTC)
SLUGS = ("a-source", "b-both", "c-content", "d-collaborative", "e-cold", "z-tie")
VARIANTS = {
    "popularity": (
        "Full catalog minus saved selections; ignores reactions/played/wishlist. "
        "Uses popularity_baseline, then diagnostic-only (-units, slug), then top-K. "
        "No content/support requirement or fallback."
    ),
    "content": (
        "Native ContentRanker: positive quantized content, minus saved selections; "
        "ignores feedback. (-base, -content, -popularity, slug), then top-K. "
        "Zero content stays ineligible; empty reason is no_content_support."
    ),
    "feedback": (
        "Native FeedbackRanker: effective content candidates minus saved/positive/disliked "
        "games before top-K. (-final, -pre-played, -base, -affinity, -content, "
        "-popularity, slug). Weights base/affinity 90/10 when active, otherwise 100/0; "
        "one played factor. Empty reason distinguishes no content from all excluded."
    ),
    "collaborative": (
        "Native CollaborativeScorer: retained neighbors of supported query sources minus "
        "all query sources and dislikes. (-score, slug); diagnostic takes top-K after "
        "native exclusions/order. No content or played adjustment; absent support returns "
        "an explicit reason and no rows. Mean uses only contributing retained edges."
    ),
    "hybrid": (
        "Native HybridRanker: content/retained-neighbor union minus saved/positive/disliked "
        "games before top-K. (-final, -pre-played, -base contribution, -collaborative "
        "contribution, -affinity contribution, -content, -popularity, slug). Request-wide "
        "base/affinity/collaborative 80/10/10 or 90/0/10; missing edge retains its weight "
        "with zero contribution. One played factor; no support wraps exact Stage 4."
    ),
}


def reaction(slug, value):
    return ActiveGameFeedback(game_slug=slug, reaction=value, reaction_occurred_at=BUILT_AT)


def scenarios():
    saved = UserContext(selected_game_slugs=("a-source",), preferred_platforms=("pc",), top_k=20)
    return (
        (
            "supported_played",
            saved,
            (reaction("a-source", "liked"), ActiveGameFeedback("b-both", played=True)),
        ),
        ("saved_only_tied", saved, ()),
        (
            "cold_user",
            UserContext(preferred_genres=("strategy",), preferred_platforms=("pc",), top_k=20),
            (),
        ),
        ("cold_source_empty", UserContext(selected_game_slugs=("e-cold",), top_k=20), ()),
        ("mixed_sources", saved, (reaction("e-cold", "liked"),)),
        (
            "cold_content_item",
            UserContext(
                selected_game_slugs=("a-source",),
                preferred_genres=("sandbox",),
                preferred_platforms=("pc",),
                top_k=20,
            ),
            (),
        ),
        (
            "all_eligible_excluded",
            saved,
            (
                reaction("c-content", "liked"),
                reaction("b-both", "disliked"),
                reaction("d-collaborative", "disliked"),
                reaction("z-tie", "disliked"),
            ),
        ),
        (
            "exclusions_top_one",
            UserContext(selected_game_slugs=("a-source",), preferred_platforms=("pc",), top_k=1),
            (
                reaction("b-both", "disliked"),
                reaction("z-tie", "liked"),
                ActiveGameFeedback("c-content", played=True),
            ),
        ),
    )


def build_models(root: Path, *, reverse=False):
    items = []
    for slug, signal in zip(SLUGS, (100, 50, 0, 100, 0, 50), strict=True):
        tactical = slug not in {"d-collaborative", "e-cold"}
        word = "tactical" if tactical else ("orbital" if slug == "d-collaborative" else "silent")
        items.append(
            CatalogItem(
                slug=slug,
                title=word,
                description=word,
                developer=None,
                publisher=None,
                average_rating=8.0,
                rating_count=100,
                popularity_score=signal,
                genres=(TaxonomyValue("strategy", "Strategy"),)
                if tactical
                else ((TaxonomyValue("sandbox", "Sandbox"),) if slug == "e-cold" else ()),
                platforms=(TaxonomyValue("pc", "PC"),),
            )
        )
    snapshot = canonical_snapshot(reversed(items) if reverse else items)
    content = load_artifact(build_artifact(snapshot, root / "content", built_at=BUILT_AT))
    # Ten synthetic profiles / five supported items cross the real bundle gate.
    # Eight share the core; two bridge c to b/z, leaving a->c absent and e cold.
    profiles = (("a-source", "b-both", "d-collaborative", "z-tie"),) * 8 + (
        ("b-both", "c-content", "z-tie"),
    ) * 2
    if reverse:
        profiles = tuple(tuple(reversed(row)) for row in reversed(profiles))
    catalog_slugs = frozenset(content.slug_to_row)
    canonical = canonicalize_profiles(profiles, catalog_slugs=catalog_slugs)
    neighborhoods = fit_collaborative_neighborhoods(profiles, catalog_slugs=catalog_slugs)
    artifact_root = build_collaborative_artifact(
        neighborhoods,
        root / "collaborative",
        metadata=CollaborativeBuildMetadata(
            source_kind="fixture",
            catalog_fingerprint=content.data_fingerprint,
            interaction_fingerprint=profile_fingerprint(canonical),
            build_id="stage5-9d-diagnostic-v1",
            built_at=BUILT_AT,
            fixture_id="stage-5-9d-six-games-v1",
            valid_until=datetime(2099, 1, 1, tzinfo=UTC),
        ),
        allow_fixture=True,
    )
    collaborative = load_collaborative_artifact(
        artifact_root,
        allow_fixture=True,
        expected_catalog_fingerprint=content.data_fingerprint,
        now=BUILT_AT,
    )
    return content, collaborative


def semantic_arrays(content, collaborative):
    return {
        "content.data": content.matrix.data,
        "content.indices": content.matrix.indices,
        "content.indptr": content.matrix.indptr,
        "content.idf": content.vectorizer.idf_,
        "content.popularity": content.popularity,
        **{
            "collaborative." + name: getattr(collaborative, name)
            for name in (
                "item_support",
                "neighbor_indices",
                "neighbor_indptr",
                "similarity_units",
                "pair_support",
            )
        },
    }


def _row(item, variant):
    base = item.components if variant == "content" else item.base_components
    result = {
        "slug": item.slug,
        "rank": item.rank,
        "origin": getattr(item, "candidate_origin", "content"),
        "base_components": [asdict(component) for component in base],
        "base": item.final_score_units if variant == "content" else item.base_score_units,
        "affinity": None,
        "collaborative": None,
        "support": None,
        "edges": [],
        "weights": [1_000_000, 0, 0],
        "contributions": [item.final_score_units, 0, 0],
        "pre_played": item.final_score_units,
        "played_factor": 1_000_000,
        "played_delta": 0,
        "final": item.final_score_units,
    }
    if variant != "content":
        result.update(
            affinity=item.affinity_score_units if item.affinity_weight_units else None,
            weights=[item.base_weight_units, item.affinity_weight_units, 0],
            contributions=[item.base_contribution_units, item.affinity_contribution_units, 0],
            pre_played=item.pre_played_score_units,
            played_factor=item.played_factor_units,
            played_delta=item.played_delta_units,
        )
    if variant == "hybrid":
        result.update(
            collaborative=item.collaborative_score_units if item.collaborative_supported else None,
            support=item.collaborative_item_support,
            edges=[asdict(edge) for edge in item.collaborative_source_edges],
        )
        result["weights"][2] = item.collaborative_weight_units
        result["contributions"][2] = item.collaborative_contribution_units
    return result


def compare_scenario(content, collaborative, context, feedback):
    feedback_ranker = FeedbackRanker(content)
    prepared = feedback_ranker.prepare_ranking_context(context, feedback)
    scoring = CollaborativeScorer(collaborative).score(prepared.collaborative_query_context)
    content_result = feedback_ranker.content_ranker.rank(context)
    feedback_result = feedback_ranker.rank(context, feedback)
    hybrid = HybridRanker(feedback_ranker).rank(
        context, feedback, CollaborativeComponentReady(scoring)
    )
    popularity = popularity_baseline(content.items)
    popular = sorted(
        (
            (item.slug, quantize(float(score)))
            for item, score in zip(content.items, popularity, strict=True)
            if item.slug not in context.selected_game_slugs
        ),
        key=lambda pair: (-pair[1], pair[0]),
    )[: context.top_k]
    fallback = isinstance(hybrid, Stage4FallbackResult)
    if fallback:
        assert hybrid.stage_4_result == feedback_result
    return {
        "context": asdict(context),
        "feedback": [
            {key: value for key, value in asdict(row).items() if not key.endswith("occurred_at")}
            for row in sorted(feedback, key=lambda value: value.game_slug)
        ],
        "sources": [asdict(source) for source in scoring.query_sources],
        "supported_sources": list(scoring.supported_source_slugs),
        "unsupported_sources": list(scoring.unsupported_source_slugs),
        "exclusions": list(prepared.candidate_exclusion_slugs),
        "variants": {
            "popularity": {
                "reason": "recommendations" if popular else "no_eligible_candidates",
                "rows": [
                    {
                        "slug": slug,
                        "rank": rank,
                        "origin": "catalog",
                        "popularity": units,
                        "weights": [1_000_000],
                        "contributions": [units],
                        "final": units,
                    }
                    for rank, (slug, units) in enumerate(popular, 1)
                ],
            },
            "content": {
                "reason": content_result.reason,
                "rows": [_row(item, "content") for item in content_result.items],
            },
            "feedback": {
                "reason": feedback_result.reason,
                "rows": [_row(item, "feedback") for item in feedback_result.items],
            },
            "collaborative": {
                "reason": scoring.reason,
                "rows": [
                    {
                        "slug": item.slug,
                        "rank": rank,
                        "origin": "collaborative",
                        "collaborative": item.collaborative_score_units,
                        "support": item.item_support,
                        "edges": [asdict(edge) for edge in item.source_edges],
                        "weights": [1_000_000],
                        "contributions": [item.collaborative_score_units],
                        "final": item.collaborative_score_units,
                    }
                    for rank, item in enumerate(scoring.candidates[: context.top_k], 1)
                ],
            },
            "hybrid": {
                "mode": hybrid.mode,
                "fallback_reason": hybrid.fallback_reason if fallback else None,
                "reason": hybrid.stage_4_result.reason if fallback else hybrid.reason,
                "rows": [
                    _row(item, "feedback" if fallback else "hybrid")
                    for item in (hybrid.stage_4_result.items if fallback else hybrid.items)
                ],
            },
        },
    }


def build_diagnostic(root: Path, *, reverse=False):
    content, collaborative = build_models(root, reverse=reverse)
    arrays = semantic_arrays(content, collaborative)
    report = {
        "fixture": "stage-5-9d-six-games-v1",
        "catalog_fingerprint": content.data_fingerprint,
        "interaction_fingerprint": collaborative.interaction_fingerprint,
        "build_id": collaborative.build_id,
        "content_model": [content.model_name, content.model_version],
        "collaborative_model": [collaborative.model_name, collaborative.model_version],
        "content_item_axis": [item.slug for item in content.items],
        "collaborative_item_axis": list(collaborative.item_slugs),
        "vocabulary_sha256": hashlib.sha256(
            json.dumps(dict(content.vectorizer.vocabulary_), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "scoring_policy": asdict(CollaborativeScorer(collaborative).identity),
        "feedback_policy": asdict(FeedbackRanker(content).identity),
        "hybrid_policy": asdict(HybridRanker(FeedbackRanker(content)).identity),
        "popularity_config": POPULARITY_CONFIG.to_dict(),
        "content_config": RANKING_CONFIG.to_dict(),
        "semantic_arrays": {
            name: {
                "dtype": str(array.dtype),
                "shape": list(array.shape),
                "sha256": hashlib.sha256(array.tobytes()).hexdigest(),
            }
            for name, array in arrays.items()
        },
        "scenarios": {
            name: compare_scenario(
                content, collaborative, context, tuple(reversed(feedback)) if reverse else feedback
            )
            for name, context, feedback in scenarios()
        },
    }
    return report, arrays


def render_diagnostic(report):
    metadata = {key: value for key, value in report.items() if key != "scenarios"}
    lines = [
        "# Stage 5 / 9D functional diagnostic",
        "",
        "Project-authored six-game fixture. Functional arithmetic only; "
        "Stage 6 evaluation remains deferred.",
        "",
        "## Provenance",
        "",
        "```json",
        json.dumps(metadata, indent=2),
        "```",
        "",
        "## Variant contracts",
        "",
        *[f"- **{name}**: {contract}" for name, contract in VARIANTS.items()],
        "",
        "All units use scale 1000000 and half-up rounding. `—` means absent/inapplicable; "
        "missing hybrid edges retain a zero contribution, not a measured score. "
        "Base cells list content/platform/popularity as raw:weight:contribution. "
        "Outer weights/contributions are base/affinity/collaborative "
        "(single component for pure variants). "
        "Played cells are factor:delta. Edge cells are source:kind:similarity:pair-support. "
        "Every table contains all returned rows; top-K and exclusions appear in its context.",
        "",
        "## Hand derivation and observed differences",
        "",
        "All six ratings are 8 with 100 votes, so the normalized rating signal is 0.5. "
        "Popularity is 0.7*0.5 + 0.3*(catalog signal/100): 350000, 500000 or 650000 units. "
        "The four tactical documents are identical; orbital and sandbox documents are "
        "orthogonal to them. A tactical unigram query has cosine "
        "(1+ln(3))/sqrt(2*(1+ln(3))^2+(1+ln(2))^2+3), or 547825 units. "
        "The cold-item scenario uses the existing 65/35 saved/taxonomy mixture, "
        "yielding content cosines 880471 (tactical) and 259724 (sandbox).",
        "",
        "Ten synthetic profiles produce item supports a/d=8, b/z=10, c=2; e is absent. "
        "Pairs a-d=8 and a-b/a-z=8 give cosines 1000000 and 894427. Pair c-z=2 gives "
        "447214; a-c is absent. In the top-one scenario, d averages the two retained "
        "source edges to 947214; c uses only its retained z edge, without dilution.",
        "",
        "For b in supported_played, base is 800000+100000+50000=950000. "
        "Feedback applies (855000+100000)*0.5=477500; hybrid applies "
        "(760000+100000+89443)*0.5, rounded once to 474722. The source liked and saved "
        "as a is counted once. Candidate c has no a edge: its hybrid contributions stay "
        "748000+100000+0=848000 under 80/10/10. Candidate d has zero content yet joins "
        "the hybrid union with base 165000 and final 132000+0+100000=232000. "
        "Content/feedback omit d because their content eligibility is unchanged. "
        "Wishlist neutrality is checked by full-result equality in the focused suite. "
        "These differences describe arithmetic and eligibility only.",
        "",
    ]

    def cell(value):
        if value is None:
            return "—"
        if isinstance(value, (list, tuple)):
            return "/".join(str(part) for part in value)
        return str(value)

    for name, scenario in report["scenarios"].items():
        details = {key: value for key, value in scenario.items() if key != "variants"}
        lines += [
            f"## {name}",
            "",
            "```json",
            json.dumps(details, separators=(",", ":")),
            "```",
            "",
            "| Variant / reason | Rank / game / origin | Base components | "
            "Base / affinity / collaborative | Support / edges | Weights | Contributions | "
            "Pre-played | Played | Final |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for variant, result in scenario["variants"].items():
            reason = result["reason"]
            if result.get("fallback_reason"):
                reason += "; stage_4_fallback: " + result["fallback_reason"]
            if not result["rows"]:
                lines.append(f"| {variant}: {reason} | empty | — | — | — | — | — | — | — | — |")
            for row in result["rows"]:
                base = (
                    " / ".join(
                        f"{c['raw_units']}:{c['weight_units']}:{c['contribution_units']}"
                        for c in row.get("base_components", [])
                    )
                    or "—"
                )
                raw = "/".join(cell(row.get(key)) for key in ("base", "affinity", "collaborative"))
                if variant == "popularity":
                    raw = "popularity=" + str(row["popularity"])
                edges = (
                    ", ".join(
                        f"{e['source_slug']}:{e['source_kind']}:{e['similarity_units']}:{e['pair_support']}"
                        for e in row.get("edges", [])
                    )
                    or "—"
                )
                cells = [
                    f"{variant}: {reason}",
                    f"{row['rank']} / {row['slug']} / {row['origin']}",
                    base,
                    raw,
                    f"{cell(row.get('support'))} / {edges}",
                    cell(row["weights"]),
                    cell(row["contributions"]),
                    cell(row.get("pre_played")),
                    f"{cell(row.get('played_factor'))}:{cell(row.get('played_delta'))}",
                    cell(row["final"]),
                ]
                lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reverse", action="store_true", help="Permute equivalent input order")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="gamelens-9d-") as directory:
        diagnostic, _ = build_diagnostic(Path(directory), reverse=args.reverse)
        print(render_diagnostic(diagnostic))
