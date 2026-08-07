import math

import numpy as np

from gamelens_recommender.config import POPULARITY_CONFIG, SCORE_SCALE, PopularityConfig
from gamelens_recommender.schemas import CatalogItem


def _min_max(values: np.ndarray, constant_units: int) -> np.ndarray:
    minimum = float(values.min())
    maximum = float(values.max())
    if math.isclose(minimum, maximum, rel_tol=0.0, abs_tol=1e-15):
        return np.full_like(values, constant_units / SCORE_SCALE, dtype=np.float64)
    return (values - minimum) / (maximum - minimum)


def popularity_baseline(
    items: tuple[CatalogItem, ...], config: PopularityConfig = POPULARITY_CONFIG
) -> np.ndarray:
    config.validate()
    if not items:
        raise ValueError("Popularity baseline requires catalog items")
    weighted_sum = sum(
        (item.average_rating or 0.0) * item.rating_count
        for item in items
        if item.average_rating is not None
    )
    total_votes = sum(item.rating_count for item in items if item.average_rating is not None)
    catalog_mean = weighted_sum / total_votes if total_votes else 5.0
    weighted_ratings: list[float] = []
    signals: list[float] = []
    for item in items:
        votes = item.rating_count
        rating = catalog_mean if item.average_rating is None else item.average_rating
        prior = config.minimum_vote_prior
        weighted = (votes / (votes + prior)) * (rating / 10) + (prior / (votes + prior)) * (
            catalog_mean / 10
        )
        weighted_ratings.append(weighted)
        signals.append(item.popularity_score)
    rating_normalized = _min_max(
        np.asarray(weighted_ratings, dtype=np.float64),
        config.constant_range_value_units,
    )
    signal_normalized = _min_max(
        np.asarray(signals, dtype=np.float64),
        config.constant_range_value_units,
    )
    scores = (
        rating_normalized * config.rating_weight_units
        + signal_normalized * config.signal_weight_units
    ) / SCORE_SCALE
    if not np.isfinite(scores).all() or np.any(scores < 0) or np.any(scores > 1):
        raise ValueError("Popularity baseline produced invalid values")
    return scores.astype(np.float64)
