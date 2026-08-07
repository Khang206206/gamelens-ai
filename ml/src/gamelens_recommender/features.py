import re
import unicodedata

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from gamelens_recommender.config import FEATURE_CONFIG, FeatureConfig
from gamelens_recommender.schemas import CatalogItem, normalize_text


def _words(value: str, config: FeatureConfig = FEATURE_CONFIG) -> str:
    normalized = normalize_text(value)
    if config.lowercase:
        normalized = normalized.lower()
    if config.strip_accents == "unicode":
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFKD", normalized)
            if not unicodedata.combining(character)
        )
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _field_token(prefix: str, slug: str) -> str:
    return f"{prefix}_{slug.replace('-', '_')}"


def build_content_document(item: CatalogItem, config: FeatureConfig = FEATURE_CONFIG) -> str:
    parts: list[str] = []
    parts.extend([_words(item.title, config)] * config.title_repetitions)
    for genre in item.genres:
        parts.extend([_field_token("genre", genre.slug)] * config.genre_repetitions)
    for tag in item.tags:
        parts.extend([_field_token("tag", tag.slug)] * config.tag_repetitions)
    for prefix, value in (("developer", item.developer), ("publisher", item.publisher)):
        if value:
            token = f"{prefix}_{_words(value, config).replace(' ', '_')}"
            parts.extend([token] * config.studio_repetitions)
    parts.extend([_words(item.description, config)] * config.description_repetitions)
    return " ".join(part for part in parts if part)


def build_preference_document(genres: tuple[str, ...], tags: tuple[str, ...]) -> str:
    tokens = [_field_token("genre", slug) for slug in sorted(genres)]
    tokens.extend(_field_token("tag", slug) for slug in sorted(tags))
    return " ".join(tokens)


def make_vectorizer(config: FeatureConfig = FEATURE_CONFIG) -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer=config.analyzer,
        token_pattern=config.token_pattern,
        ngram_range=(config.ngram_min, config.ngram_max),
        lowercase=False,
        strip_accents=config.strip_accents,
        min_df=config.min_df,
        max_df=config.max_df,
        sublinear_tf=config.sublinear_tf,
        norm=config.norm,
        dtype=np.dtype(config.dtype),
    )


def fit_features(
    items: tuple[CatalogItem, ...], config: FeatureConfig = FEATURE_CONFIG
) -> tuple[TfidfVectorizer, sparse.csr_matrix]:
    documents = [build_content_document(item, config) for item in items]
    if not all(documents):
        raise ValueError("Every catalog item must produce a content document")
    try:
        vectorizer = make_vectorizer(config)
        matrix = vectorizer.fit_transform(documents).tocsr()
        matrix.sum_duplicates()
        matrix.sort_indices()
    except ValueError as error:
        raise ValueError("Catalog content produced an empty TF-IDF vocabulary") from error
    if matrix.shape[0] != len(items) or matrix.shape[1] == 0:
        raise ValueError("TF-IDF matrix shape does not match the catalog")
    if not np.isfinite(matrix.data).all():
        raise ValueError("TF-IDF matrix contains non-finite values")
    if np.any(np.sqrt(matrix.multiply(matrix).sum(axis=1)).A1 == 0):
        raise ValueError("TF-IDF matrix contains a zero-norm row")
    return vectorizer, matrix


def restore_vectorizer(
    vocabulary: dict[str, int], idf: np.ndarray, config: FeatureConfig = FEATURE_CONFIG
) -> TfidfVectorizer:
    vectorizer = make_vectorizer(config)
    vectorizer.vocabulary_ = vocabulary
    vectorizer.fixed_vocabulary_ = True
    vectorizer.idf_ = idf
    vectorizer.idf_.flags.writeable = False
    return vectorizer
