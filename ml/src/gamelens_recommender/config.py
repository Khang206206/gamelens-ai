from dataclasses import asdict, dataclass

ARTIFACT_SCHEMA_VERSION = "1"
MODEL_NAME = "gamelens-content-tfidf"
MODEL_VERSION = "1.0.0"
CODE_COMPATIBILITY = "stage-3-v1"
SCORE_SCALE = 1_000_000


@dataclass(frozen=True)
class FeatureConfig:
    unicode_normalization: str = "NFKC"
    lowercase: bool = True
    strip_accents: str = "unicode"
    title_repetitions: int = 2
    genre_repetitions: int = 3
    tag_repetitions: int = 3
    studio_repetitions: int = 1
    description_repetitions: int = 1
    analyzer: str = "word"
    token_pattern: str = r"(?u)\b[a-z0-9][a-z0-9_]{1,}\b"
    ngram_min: int = 1
    ngram_max: int = 2
    min_df: int = 1
    max_df: float = 1.0
    sublinear_tf: bool = True
    norm: str = "l2"
    dtype: str = "float64"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PopularityConfig:
    minimum_vote_prior: int = 50
    rating_weight_units: int = 700_000
    signal_weight_units: int = 300_000
    missing_rating_policy: str = "catalog-weighted-mean"
    constant_range_value_units: int = 500_000

    def validate(self) -> None:
        if self.minimum_vote_prior <= 0:
            raise ValueError("Popularity minimum-vote prior must be positive")
        if self.rating_weight_units < 0 or self.signal_weight_units < 0:
            raise ValueError("Popularity weights must be non-negative")
        if self.rating_weight_units + self.signal_weight_units != SCORE_SCALE:
            raise ValueError("Popularity weights must sum to the score scale")
        if not 0 <= self.constant_range_value_units <= SCORE_SCALE:
            raise ValueError("Popularity constant-range value must be bounded")
        if self.missing_rating_policy != "catalog-weighted-mean":
            raise ValueError("Popularity missing-rating policy is unsupported")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RankingConfig:
    score_scale: int = SCORE_SCALE
    selected_game_weight_units: int = 650_000
    taxonomy_weight_units: int = 350_000
    content_weight_units: int = 800_000
    platform_weight_units: int = 100_000
    popularity_weight_units: int = 100_000
    rounding: str = "half-up"
    tie_break: tuple[str, ...] = (
        "final_score_desc",
        "content_score_desc",
        "popularity_score_desc",
        "slug_asc",
    )

    def validate(self) -> None:
        weights = (
            self.selected_game_weight_units,
            self.taxonomy_weight_units,
            self.content_weight_units,
            self.platform_weight_units,
            self.popularity_weight_units,
        )
        if self.score_scale != SCORE_SCALE:
            raise ValueError("Ranking score scale is unsupported")
        if any(weight < 0 for weight in weights):
            raise ValueError("Ranking weights must be non-negative")
        component_total = (
            self.content_weight_units + self.platform_weight_units + self.popularity_weight_units
        )
        if component_total != self.score_scale:
            raise ValueError("Ranking component weights must sum to the score scale")
        if self.selected_game_weight_units + self.taxonomy_weight_units != self.score_scale:
            raise ValueError("User-vector weights must sum to the score scale")
        if self.rounding != "half-up":
            raise ValueError("Ranking rounding policy is unsupported")
        if self.tie_break != (
            "final_score_desc",
            "content_score_desc",
            "popularity_score_desc",
            "slug_asc",
        ):
            raise ValueError("Ranking tie-break policy is unsupported")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["tie_break"] = list(self.tie_break)
        return value


@dataclass(frozen=True)
class ArtifactLimits:
    max_members: int = 12
    max_member_bytes: int = 64 * 1024 * 1024
    max_total_bytes: int = 128 * 1024 * 1024
    max_items: int = 100_000
    max_vocabulary: int = 250_000
    max_matrix_nonzero: int = 20_000_000

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


FEATURE_CONFIG = FeatureConfig()
POPULARITY_CONFIG = PopularityConfig()
RANKING_CONFIG = RankingConfig()
ARTIFACT_LIMITS = ArtifactLimits()
