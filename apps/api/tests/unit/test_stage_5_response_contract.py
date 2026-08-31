import json
from copy import deepcopy
from typing import Any, get_args

import pytest
from app.schemas.personalized_recommendations import (
    PersonalizedRecommendationResponse,
    Stage5FallbackReason,
    Stage5PersonalizedRecommendationResponse,
)
from fastapi.testclient import TestClient
from gamelens_recommender import HYBRID_FALLBACK_REASONS
from pydantic import ValidationError


def _game(*, game_id: int = 7, slug: str = "starbound-couriers") -> dict[str, Any]:
    return {
        "id": game_id,
        "title": "Starbound Couriers",
        "slug": slug,
        "release_date": None,
        "developer": "Fixture Studio",
        "publisher": None,
        "average_rating": 8.5,
        "rating_count": 12,
        "popularity_score": 0.599117,
        "genres": [],
        "tags": [],
        "platforms": [],
        "cover_image_url": None,
    }


def _hybrid_item() -> dict[str, Any]:
    return {
        "rank": 1,
        "game": _game(),
        "base_ranking_score": 0.159912,
        "base_components": [
            {
                "name": "content",
                "raw_score": 0.0,
                "weight": 0.8,
                "contribution": 0.0,
            },
            {
                "name": "platform",
                "raw_score": 1.0,
                "weight": 0.1,
                "contribution": 0.1,
            },
            {
                "name": "popularity",
                "raw_score": 0.599117,
                "weight": 0.1,
                "contribution": 0.059912,
            },
        ],
        "base_weight": 0.8,
        "base_contribution": 0.12793,
        "feedback_affinity_score": 0.0,
        "feedback_affinity_weight": 0.1,
        "feedback_affinity_contribution": 0.0,
        "candidate_origin": "collaborative",
        "collaborative_supported": True,
        "collaborative_score": 0.428571,
        "collaborative_weight": 0.1,
        "collaborative_contribution": 0.042857,
        "collaborative_item_support": 12,
        "collaborative_source_edges": [
            {
                "source_game_slug": "emberfall-tactics",
                "source_kind": "liked",
                "similarity_score": 0.428571,
                "pair_support": 3,
            }
        ],
        "pre_played_score": 0.170787,
        "played_factor": 1.0,
        "played_delta": 0.0,
        "ranking_score": 0.170787,
        "adjustment_reasons": [
            "feedback_affinity",
            "collaborative_similarity",
        ],
        "evidence": {
            "matching_genres": [],
            "matching_tags": [],
            "preferred_platforms": [],
            "similar_selected_games": [],
            "popularity_score": 0.599117,
        },
        "explanation": {
            "summary": "Aggregate interaction evidence contributed to this ranking.",
            "reasons": ["The result has bounded collaborative source support."],
        },
    }


def _hybrid_response() -> dict[str, Any]:
    return {
        "generation_id": "1" * 32,
        "model_name": "content-recommender",
        "model_version": "1.0.0",
        "data_fingerprint": "a" * 64,
        "policy": {
            "name": "gamelens-feedback-adjustment",
            "version": "1.0.0",
        },
        "ranking_mode": "hybrid",
        "fallback_reason": None,
        "hybrid_policy": {
            "name": "gamelens-hybrid-ranking",
            "version": "1.0.0",
        },
        "collaborative_model": {
            "name": "item-item-cosine",
            "version": "1.0.0",
            "interaction_fingerprint": "b" * 64,
            "scoring_policy": {
                "name": "gamelens-collaborative-scoring",
                "version": "1.0.0",
            },
        },
        "response_reason": "recommendations",
        "requested_top_k": 10,
        "positive_feedback_sources": [{"game_slug": "emberfall-tactics", "kind": "liked"}],
        "items": [_hybrid_item()],
    }


def _fallback_item() -> dict[str, Any]:
    return {
        "rank": 1,
        "game": _game(slug="content-supported-game"),
        "base_ranking_score": 0.4,
        "base_components": [
            {
                "name": "content",
                "raw_score": 0.5,
                "weight": 0.8,
                "contribution": 0.4,
            },
            {
                "name": "platform",
                "raw_score": 0.0,
                "weight": 0.1,
                "contribution": 0.0,
            },
            {
                "name": "popularity",
                "raw_score": 0.0,
                "weight": 0.1,
                "contribution": 0.0,
            },
        ],
        "base_weight": 1.0,
        "base_contribution": 0.4,
        "feedback_affinity_score": 0.0,
        "feedback_affinity_weight": 0.0,
        "feedback_affinity_contribution": 0.0,
        "candidate_origin": "content",
        "collaborative_supported": False,
        "collaborative_score": 0.0,
        "collaborative_weight": 0.0,
        "collaborative_contribution": 0.0,
        "collaborative_item_support": None,
        "collaborative_source_edges": [],
        "pre_played_score": 0.4,
        "played_factor": 1.0,
        "played_delta": 0.0,
        "ranking_score": 0.4,
        "adjustment_reasons": [],
        "evidence": {
            "matching_genres": [],
            "matching_tags": [],
            "preferred_platforms": [],
            "similar_selected_games": [],
            "popularity_score": 0.0,
        },
        "explanation": {
            "summary": "Content evidence determined this ranking.",
            "reasons": ["The existing personalized ranking remained available."],
        },
    }


def _fallback_response(reason: str = "not_configured") -> dict[str, Any]:
    payload = _hybrid_response()
    payload.update(
        {
            "ranking_mode": "stage_4_fallback",
            "fallback_reason": reason,
            "hybrid_policy": None,
            "collaborative_model": None,
            "items": [_fallback_item()],
        }
    )
    return payload


def test_stage_5_hybrid_contract_serializes_exact_bounded_evidence() -> None:
    response = Stage5PersonalizedRecommendationResponse.model_validate(_hybrid_response())

    body = response.model_dump(mode="json")
    encoded = response.model_dump_json()

    assert body["ranking_mode"] == "hybrid"
    assert body["fallback_reason"] is None
    assert body["items"][0]["candidate_origin"] == "collaborative"
    assert body["items"][0]["collaborative_item_support"] == 12
    assert body["items"][0]["collaborative_source_edges"] == [
        {
            "source_game_slug": "emberfall-tactics",
            "source_kind": "liked",
            "similarity_score": 0.428571,
            "pair_support": 3,
        }
    ]
    assert '"collaborative_score":0.428571' in encoded
    assert '"collaborative_contribution":0.042857' in encoded
    assert json.loads(encoded) == body


def test_stage_5_fallback_taxonomy_matches_the_hybrid_policy_contract() -> None:
    assert get_args(Stage5FallbackReason) == HYBRID_FALLBACK_REASONS
    for reason in HYBRID_FALLBACK_REASONS:
        response = Stage5PersonalizedRecommendationResponse.model_validate(
            _fallback_response(reason)
        )
        assert response.fallback_reason == reason
        assert response.collaborative_model is None
        assert response.items[0].collaborative_source_edges == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fallback_reason", "not_configured"),
        ("hybrid_policy", None),
        ("collaborative_model", None),
        ("response_reason", "no_content_support"),
    ],
)
def test_hybrid_mode_requires_complete_truthful_identity(field: str, value: object) -> None:
    payload = _hybrid_response()
    payload[field] = value

    with pytest.raises(ValidationError):
        Stage5PersonalizedRecommendationResponse.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fallback_reason", None),
        ("hybrid_policy", {"name": "gamelens-hybrid-ranking", "version": "1.0.0"}),
        ("collaborative_model", _hybrid_response()["collaborative_model"]),
    ],
)
def test_fallback_mode_cannot_claim_hybrid_component_identity(
    field: str,
    value: object,
) -> None:
    payload = _fallback_response()
    payload[field] = value

    with pytest.raises(ValidationError):
        Stage5PersonalizedRecommendationResponse.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("collaborative_score",), 0.428572),
        (("collaborative_score",), 0.4285711),
        (("collaborative_item_support",), None),
        (("candidate_origin",), "content"),
        (("adjustment_reasons",), ["feedback_affinity"]),
    ],
)
def test_hybrid_item_rejects_incomplete_or_nonreconstructible_evidence(
    path: tuple[str, ...],
    value: object,
) -> None:
    payload = _hybrid_response()
    item = payload["items"][0]
    assert isinstance(item, dict)
    item[path[0]] = value

    with pytest.raises(ValidationError):
        Stage5PersonalizedRecommendationResponse.model_validate(payload)


def test_hybrid_item_rejects_unordered_duplicate_or_impossible_edges() -> None:
    payload = _hybrid_response()
    item = payload["items"][0]
    assert isinstance(item, dict)
    item["collaborative_score"] = 0.35
    item["collaborative_contribution"] = 0.035
    item["pre_played_score"] = 0.16293
    item["ranking_score"] = 0.16293
    item["collaborative_source_edges"] = [
        {
            "source_game_slug": "second-source",
            "source_kind": "saved_game",
            "similarity_score": 0.3,
            "pair_support": 13,
        },
        {
            "source_game_slug": "emberfall-tactics",
            "source_kind": "liked",
            "similarity_score": 0.4,
            "pair_support": 3,
        },
    ]

    with pytest.raises(ValidationError):
        Stage5PersonalizedRecommendationResponse.model_validate(payload)

    payload = _hybrid_response()
    item = payload["items"][0]
    assert isinstance(item, dict)
    item["collaborative_source_edges"] = [
        item["collaborative_source_edges"][0],
        deepcopy(item["collaborative_source_edges"][0]),
    ]

    with pytest.raises(ValidationError):
        Stage5PersonalizedRecommendationResponse.model_validate(payload)


def test_stage_5_response_forbids_identity_leakage_and_unbounded_shapes() -> None:
    payload = _hybrid_response()
    payload["user_id"] = 42
    with pytest.raises(ValidationError):
        Stage5PersonalizedRecommendationResponse.model_validate(payload)

    payload = _hybrid_response()
    collaborative_model = payload["collaborative_model"]
    assert isinstance(collaborative_model, dict)
    collaborative_model["build_id"] = "internal-build"
    with pytest.raises(ValidationError):
        Stage5PersonalizedRecommendationResponse.model_validate(payload)

    payload = _hybrid_response()
    item = payload["items"][0]
    assert isinstance(item, dict)
    edge = item["collaborative_source_edges"][0]
    item["collaborative_source_edges"] = [
        {
            **edge,
            "source_game_slug": f"source-{index}",
        }
        for index in range(11)
    ]
    with pytest.raises(ValidationError):
        Stage5PersonalizedRecommendationResponse.model_validate(payload)


def test_stage_4_schema_remains_valid_while_saved_openapi_activates_stage_5(
    client: TestClient,
) -> None:
    fallback = _fallback_response()
    legacy_payload = {
        key: value
        for key, value in fallback.items()
        if key
        not in {
            "ranking_mode",
            "fallback_reason",
            "hybrid_policy",
            "collaborative_model",
        }
    }
    legacy_payload["items"] = [
        {
            key: value
            for key, value in fallback["items"][0].items()
            if key
            not in {
                "candidate_origin",
                "collaborative_supported",
                "collaborative_score",
                "collaborative_weight",
                "collaborative_contribution",
                "collaborative_item_support",
                "collaborative_source_edges",
            }
        }
    ]

    legacy = PersonalizedRecommendationResponse.model_validate(legacy_payload)
    assert legacy.model_dump(mode="json") == legacy_payload

    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/me/recommendations"]["post"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/Stage5PersonalizedRecommendationResponse")
    assert "Stage5PersonalizedRecommendationResponse" in schema["components"]["schemas"]
