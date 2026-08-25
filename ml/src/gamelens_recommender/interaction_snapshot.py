from __future__ import annotations

import hashlib
import itertools
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LABEL_POLICY_ID = "gamelens-collaborative-labels/1.0.0"
AUDIT_SCHEMA_VERSION = 1
FIXTURE_SCHEMA_VERSION = 1
MIN_PROFILE_ITEMS = 2
MIN_ITEM_SUPPORT = 2
MIN_PAIR_SUPPORT = 2
MIN_ACTIVATION_USERS = 10
MIN_ACTIVATION_EDGES = 20
MIN_ACTIVATION_ITEMS = 5
MAX_PROFILES = 500_000
MAX_UNIQUE_ITEMS = 100_000
MAX_POSITIVE_EDGES = 2_000_000
MAX_PAIR_CONTRIBUTIONS = 10_000_000
MAX_DISTINCT_PAIRS = 1_000_000
MAX_FIXTURE_BYTES = 1_000_000
ALLOWED_EXCLUSION_REASONS = frozenset(
    {
        "disliked",
        "low_rating",
        "played_only",
        "viewed_only",
        "wishlisted_only",
        "unknown_game",
    }
)
_FIXTURE_ROOT_KEYS = frozenset(
    {
        "fixture_schema_version",
        "fixture_id",
        "source_kind",
        "label_policy",
        "provenance",
        "profiles",
        "cold_start",
        "expected_audit",
    }
)
_PROFILE_KEYS = frozenset({"profile_key", "positive_game_slugs", "excluded"})
_EXCLUSION_KEYS = frozenset({"game_slug", "reason"})
_COLD_START_KEYS = frozenset({"empty_profile_key", "unsupported_game_slug"})
_EXPECTED_AUDIT_KEYS = frozenset(
    {
        "candidate_profiles",
        "candidate_positive_edges",
        "distinct_candidate_items",
        "ready_for_functional_build",
        "interaction_fingerprint",
        "fixture_contract_fingerprint",
        "exclusion_counts",
        "retained_contributors",
        "retained_items",
        "retained_positive_edges",
        "pair_contributions",
        "distinct_pairs",
        "supported_pairs",
    }
)


class SnapshotAuditError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FixtureSnapshot:
    fixture_id: str
    profiles: tuple[tuple[str, ...], ...]
    exclusion_counts: dict[str, int]
    expected_audit: dict[str, object]
    unsupported_game_slug: str
    contract_fingerprint: str


@dataclass(frozen=True)
class SupportedProfiles:
    """Identity-free bipartite two-core retained by the support policy."""

    profiles: tuple[tuple[str, ...], ...]
    item_support: tuple[tuple[str, int], ...]
    fixed_point_passes: int


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SnapshotAuditError("fixture_invalid", f"Duplicate fixture key: {key}")
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> None:
    raise SnapshotAuditError(
        "fixture_invalid", f"Fixture contains a non-finite JSON constant: {value}"
    )


def _bucket_counts(values: Iterable[int]) -> dict[str, int]:
    buckets = {"0": 0, "1": 0, "2": 0, "3-4": 0, "5-9": 0, "10+": 0}
    for value in values:
        if value <= 0:
            buckets["0"] += 1
        elif value == 1:
            buckets["1"] += 1
        elif value == 2:
            buckets["2"] += 1
        elif value <= 4:
            buckets["3-4"] += 1
        elif value <= 9:
            buckets["5-9"] += 1
        else:
            buckets["10+"] += 1
    return buckets


def canonicalize_profiles(
    profiles: Iterable[Iterable[str]],
    *,
    catalog_slugs: frozenset[str],
) -> tuple[tuple[str, ...], ...]:
    canonical: list[tuple[str, ...]] = []
    edge_count = 0
    distinct_items: set[str] = set()
    for raw_profile in profiles:
        values = tuple(sorted(set(raw_profile)))
        if any(not value or value != value.strip() for value in values):
            raise SnapshotAuditError("snapshot_invalid", "Game slugs must be non-empty and trimmed")
        unknown = set(values) - catalog_slugs
        if unknown:
            raise SnapshotAuditError("catalog_mismatch", "Snapshot contains an unknown game slug")
        edge_count += len(values)
        if edge_count > MAX_POSITIVE_EDGES:
            raise SnapshotAuditError("snapshot_limit_exceeded", "Positive edge limit exceeded")
        distinct_items.update(values)
        if len(distinct_items) > MAX_UNIQUE_ITEMS:
            raise SnapshotAuditError("snapshot_limit_exceeded", "Unique item limit exceeded")
        canonical.append(values)
        if len(canonical) > MAX_PROFILES:
            raise SnapshotAuditError(
                "snapshot_limit_exceeded", "Contributor profile limit exceeded"
            )
    return tuple(sorted(canonical))


def profile_fingerprint(profiles: Sequence[tuple[str, ...]]) -> str:
    payload = {
        "label_policy": LABEL_POLICY_ID,
        "profiles": [list(profile) for profile in sorted(profiles)],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def prune_supported_profiles(
    profiles: Sequence[tuple[str, ...]],
    *,
    minimum_profile_items: int = MIN_PROFILE_ITEMS,
    minimum_item_support: int = MIN_ITEM_SUPPORT,
) -> SupportedProfiles:
    """Apply the deterministic queue-based bipartite support filter.

    The caller owns canonicalization. Duplicate profile rows are deliberately
    retained because they represent distinct identity-free contributors.
    """

    if (
        type(minimum_profile_items) is not int
        or minimum_profile_items < 1
        or type(minimum_item_support) is not int
        or minimum_item_support < 1
    ):
        raise SnapshotAuditError("snapshot_invalid", "Support thresholds must be positive integers")

    multi_profiles = [profile for profile in profiles if len(profile) >= minimum_profile_items]
    initial_item_support = Counter(item for profile in multi_profiles for item in profile)
    profile_items = [set(profile) for profile in multi_profiles]
    item_profiles: defaultdict[str, list[int]] = defaultdict(list)
    for profile_index, items in enumerate(profile_items):
        for item in items:
            item_profiles[item].append(profile_index)

    active_profiles = [True] * len(multi_profiles)
    active_items = set(item_profiles)
    active_item_support = dict(initial_item_support)
    pending_items = {
        item for item, support in active_item_support.items() if support < minimum_item_support
    }
    pruning_rounds = 0
    while pending_items:
        pruning_rounds += 1
        affected_profiles: set[int] = set()
        for item in sorted(pending_items):
            if item not in active_items:
                continue
            active_items.remove(item)
            for profile_index in item_profiles[item]:
                if active_profiles[profile_index] and item in profile_items[profile_index]:
                    profile_items[profile_index].remove(item)
                    affected_profiles.add(profile_index)
        next_pending: set[str] = set()
        for profile_index in sorted(affected_profiles):
            if (
                active_profiles[profile_index]
                and len(profile_items[profile_index]) < minimum_profile_items
            ):
                active_profiles[profile_index] = False
                for item in sorted(profile_items[profile_index]):
                    active_item_support[item] -= 1
                    if active_item_support[item] == 0:
                        active_items.discard(item)
                        next_pending.discard(item)
                    elif active_item_support[item] < minimum_item_support:
                        next_pending.add(item)
                profile_items[profile_index].clear()
        pending_items = next_pending

    retained_profiles = tuple(
        tuple(item for item in profile if item in active_items)
        for profile_index, profile in enumerate(multi_profiles)
        if active_profiles[profile_index]
    )
    final_item_support = Counter(item for profile in retained_profiles for item in profile)
    return SupportedProfiles(
        profiles=retained_profiles,
        item_support=tuple(sorted(final_item_support.items())),
        fixed_point_passes=pruning_rounds + 1,
    )


def audit_profiles(
    profiles: Sequence[tuple[str, ...]],
    *,
    source_kind: str,
    catalog_fingerprint: str,
    exclusion_counts: dict[str, int] | None = None,
    cutoff: str | None = None,
    data_revision: int | None = None,
    consent_version: str | None = None,
) -> dict[str, object]:
    if source_kind not in {"fixture", "live"}:
        raise SnapshotAuditError("source_kind_invalid", "Unsupported interaction source kind")
    if len(catalog_fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in catalog_fingerprint
    ):
        raise SnapshotAuditError(
            "catalog_mismatch", "Catalog fingerprint must be lowercase SHA-256"
        )

    sizes = [len(profile) for profile in profiles]
    multi_profiles = [profile for profile in profiles if len(profile) >= MIN_PROFILE_ITEMS]
    initial_item_support = Counter(item for profile in multi_profiles for item in profile)
    supported = prune_supported_profiles(multi_profiles)
    retained_profiles = supported.profiles
    final_item_support = dict(supported.item_support)
    retained_edges = sum(map(len, retained_profiles))
    pair_contributions = sum(
        len(profile) * (len(profile) - 1) // 2 for profile in retained_profiles
    )
    if pair_contributions > MAX_PAIR_CONTRIBUTIONS:
        raise SnapshotAuditError("snapshot_limit_exceeded", "Pair contribution limit exceeded")
    pair_support: Counter[tuple[str, str]] = Counter()
    for profile in retained_profiles:
        for pair in itertools.combinations(profile, 2):
            if pair not in pair_support and len(pair_support) >= MAX_DISTINCT_PAIRS:
                raise SnapshotAuditError("snapshot_limit_exceeded", "Distinct pair limit exceeded")
            pair_support[pair] += 1
    supported_pairs = sum(support >= MIN_PAIR_SUPPORT for support in pair_support.values())
    retained_items = len(final_item_support)
    denominator = len(retained_profiles) * retained_items

    reasons: list[str] = []
    if not profiles:
        reasons.append("no_contributors")
    if not multi_profiles:
        reasons.append("no_multi_positive_users")
    if not final_item_support:
        reasons.append("unsupported_items")
    if not supported_pairs:
        reasons.append("no_supported_pairs")
    if len(retained_profiles) < MIN_ACTIVATION_USERS:
        reasons.append("insufficient_activation_users")
    if retained_edges < MIN_ACTIVATION_EDGES:
        reasons.append("insufficient_activation_edges")
    if retained_items < MIN_ACTIVATION_ITEMS:
        reasons.append("insufficient_activation_items")
    ready = not reasons

    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "source_kind": source_kind,
        "status": "ready_for_functional_build" if ready else "insufficient_data",
        "ready_for_functional_build": ready,
        "approved_live_training_eligibility": False,
        "reasons": reasons,
        "label_policy": LABEL_POLICY_ID,
        "catalog_fingerprint": catalog_fingerprint,
        "interaction_fingerprint": profile_fingerprint(profiles),
        "cutoff": cutoff,
        "data_revision": data_revision,
        "consent_version": consent_version,
        "candidate_profiles": {
            "contributors": len(profiles),
            "positive_edges": sum(sizes),
            "distinct_items": len({item for profile in profiles for item in profile}),
            "profile_size_distribution": _bucket_counts(sizes),
        },
        "exclusion_counts": dict(sorted((exclusion_counts or {}).items())),
        "support_filter": {
            "algorithm": "deterministic-queue-bipartite-two-core-v1",
            "fixed_point_passes": supported.fixed_point_passes,
            "retained_contributors": len(retained_profiles),
            "retained_items": retained_items,
            "retained_positive_edges": retained_edges,
            "item_support_distribution_before_filter": _bucket_counts(
                initial_item_support.values()
            ),
            "item_support_distribution_after_filter": _bucket_counts(final_item_support.values()),
            "matrix_density": {
                "numerator": retained_edges,
                "denominator": denominator,
                "rate": round(retained_edges / denominator, 12) if denominator else None,
            },
        },
        "pair_support": {
            "pair_contributions": pair_contributions,
            "distinct_pairs": len(pair_support),
            "supported_pairs": supported_pairs,
            "distribution": _bucket_counts(pair_support.values()),
        },
        "thresholds": {
            "minimum_profile_items": MIN_PROFILE_ITEMS,
            "minimum_item_support": MIN_ITEM_SUPPORT,
            "minimum_pair_support": MIN_PAIR_SUPPORT,
            "activation_minimum_users": MIN_ACTIVATION_USERS,
            "activation_minimum_edges": MIN_ACTIVATION_EDGES,
            "activation_minimum_items": MIN_ACTIVATION_ITEMS,
        },
        "limits": {
            "maximum_profiles": MAX_PROFILES,
            "maximum_unique_items": MAX_UNIQUE_ITEMS,
            "maximum_positive_edges": MAX_POSITIVE_EDGES,
            "maximum_pair_contributions": MAX_PAIR_CONTRIBUTIONS,
            "maximum_distinct_pairs": MAX_DISTINCT_PAIRS,
        },
        "privacy": {
            "aggregate_only": True,
            "user_identifiers_emitted": False,
            "row_level_snapshot_written": False,
            "cohort_mapping_written": False,
        },
        "interpretation": (
            "Structural readiness is functional evidence only. It is not live-data approval, "
            "representativeness, recommendation quality, or permission to serve an artifact."
        ),
    }


def load_fixture(path: Path, *, catalog_slugs: frozenset[str]) -> FixtureSnapshot:
    try:
        with path.open("rb") as fixture_stream:
            raw_payload = fixture_stream.read(MAX_FIXTURE_BYTES + 1)
        if len(raw_payload) > MAX_FIXTURE_BYTES:
            raise SnapshotAuditError(
                "fixture_limit_exceeded", "Fixture exceeds the maximum byte size"
            )
        payload = json.loads(
            raw_payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
        )
    except SnapshotAuditError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SnapshotAuditError(
            "fixture_invalid", "Fixture is not readable strict JSON"
        ) from error
    if not isinstance(payload, dict):
        raise SnapshotAuditError("fixture_invalid", "Fixture root must be an object")
    if frozenset(payload) != _FIXTURE_ROOT_KEYS:
        raise SnapshotAuditError("fixture_invalid", "Fixture root keys are invalid")
    fixture_schema_version = payload.get("fixture_schema_version")
    if type(fixture_schema_version) is not int or fixture_schema_version != FIXTURE_SCHEMA_VERSION:
        raise SnapshotAuditError("fixture_invalid", "Fixture schema version is unsupported")
    if payload.get("source_kind") != "fixture" or payload.get("label_policy") != LABEL_POLICY_ID:
        raise SnapshotAuditError("fixture_invalid", "Fixture source or label policy is invalid")
    provenance = payload.get("provenance")
    if provenance != {
        "kind": "project-authored",
        "contains_real_user_data": False,
        "quality_evidence": False,
    }:
        raise SnapshotAuditError("fixture_invalid", "Fixture provenance must be project-authored")
    fixture_id = payload.get("fixture_id")
    if not isinstance(fixture_id, str) or not fixture_id.startswith("stage-5-"):
        raise SnapshotAuditError("fixture_invalid", "Fixture ID is invalid")
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, list):
        raise SnapshotAuditError("fixture_invalid", "Fixture profiles must be an array")
    profiles: list[tuple[str, ...]] = []
    contract_profiles: list[dict[str, object]] = []
    profile_keys: set[str] = set()
    exclusion_counts: Counter[str] = Counter()
    for entry in raw_profiles:
        if not isinstance(entry, dict):
            raise SnapshotAuditError("fixture_invalid", "Fixture profile must be an object")
        if frozenset(entry) != _PROFILE_KEYS:
            raise SnapshotAuditError("fixture_invalid", "Fixture profile keys are invalid")
        profile_key = entry.get("profile_key")
        positives = entry.get("positive_game_slugs")
        exclusions = entry.get("excluded")
        if (
            not isinstance(profile_key, str)
            or not profile_key.startswith("synthetic-")
            or profile_key in profile_keys
            or not isinstance(positives, list)
            or not all(isinstance(value, str) for value in positives)
            or positives != sorted(set(positives))
            or not isinstance(exclusions, list)
        ):
            raise SnapshotAuditError("fixture_invalid", "Fixture profile contract is invalid")
        profile_keys.add(profile_key)
        positive_set = set(positives)
        normalized_exclusions: list[dict[str, str]] = []
        for exclusion in exclusions:
            if not isinstance(exclusion, dict):
                raise SnapshotAuditError("fixture_invalid", "Fixture exclusion is invalid")
            if frozenset(exclusion) != _EXCLUSION_KEYS:
                raise SnapshotAuditError("fixture_invalid", "Fixture exclusion keys are invalid")
            game_slug = exclusion.get("game_slug")
            reason = exclusion.get("reason")
            if (
                not isinstance(game_slug, str)
                or game_slug in positive_set
                or reason not in ALLOWED_EXCLUSION_REASONS
            ):
                raise SnapshotAuditError("fixture_invalid", "Fixture exclusion contract is invalid")
            if (reason == "unknown_game") == (game_slug in catalog_slugs):
                raise SnapshotAuditError(
                    "fixture_invalid",
                    "Unknown-game exclusions must be outside the catalog and all others inside it",
                )
            exclusion_counts[str(reason)] += 1
            normalized_exclusions.append({"game_slug": game_slug, "reason": str(reason)})
        profiles.append(tuple(positives))
        contract_profiles.append(
            {
                "positive_game_slugs": positives,
                "excluded": sorted(
                    normalized_exclusions,
                    key=lambda value: (value["game_slug"], value["reason"]),
                ),
            }
        )
    canonical = canonicalize_profiles(profiles, catalog_slugs=catalog_slugs)
    cold_start = payload.get("cold_start")
    if not isinstance(cold_start, dict):
        raise SnapshotAuditError("fixture_invalid", "Fixture cold-start contract is missing")
    if frozenset(cold_start) != _COLD_START_KEYS:
        raise SnapshotAuditError("fixture_invalid", "Fixture cold-start keys are invalid")
    unsupported_game_slug = cold_start.get("unsupported_game_slug")
    if (
        cold_start.get("empty_profile_key") != "synthetic-cold-start"
        or not isinstance(unsupported_game_slug, str)
        or unsupported_game_slug not in catalog_slugs
        or unsupported_game_slug in {item for profile in canonical for item in profile}
    ):
        raise SnapshotAuditError("fixture_invalid", "Fixture cold-start contract is invalid")
    contract_fingerprint = hashlib.sha256(
        canonical_json_bytes(
            {
                "fixture_schema_version": fixture_schema_version,
                "fixture_id": fixture_id,
                "label_policy": LABEL_POLICY_ID,
                "profiles": sorted(contract_profiles, key=canonical_json_bytes),
                "cold_start": {
                    "empty_profile_key": cold_start["empty_profile_key"],
                    "unsupported_game_slug": unsupported_game_slug,
                },
            }
        )
    ).hexdigest()
    expected = payload.get("expected_audit")
    if not isinstance(expected, dict) or frozenset(expected) != _EXPECTED_AUDIT_KEYS:
        raise SnapshotAuditError("fixture_invalid", "Fixture expected audit contract is invalid")
    return FixtureSnapshot(
        fixture_id=fixture_id,
        profiles=canonical,
        exclusion_counts=dict(exclusion_counts),
        expected_audit=expected,
        unsupported_game_slug=unsupported_game_slug,
        contract_fingerprint=contract_fingerprint,
    )


def audit_fixture(
    path: Path,
    *,
    catalog_slugs: frozenset[str],
    catalog_fingerprint: str,
) -> dict[str, object]:
    fixture = load_fixture(path, catalog_slugs=catalog_slugs)
    report = audit_profiles(
        fixture.profiles,
        source_kind="fixture",
        catalog_fingerprint=catalog_fingerprint,
        exclusion_counts=fixture.exclusion_counts,
    )
    candidate = report["candidate_profiles"]
    support = report["support_filter"]
    pairs = report["pair_support"]
    assert isinstance(candidate, dict)
    assert isinstance(support, dict)
    assert isinstance(pairs, dict)
    observed = {
        "candidate_profiles": candidate["contributors"],
        "candidate_positive_edges": candidate["positive_edges"],
        "distinct_candidate_items": candidate["distinct_items"],
        "ready_for_functional_build": report["ready_for_functional_build"],
        "interaction_fingerprint": report["interaction_fingerprint"],
        "fixture_contract_fingerprint": fixture.contract_fingerprint,
        "exclusion_counts": report["exclusion_counts"],
        "retained_contributors": support["retained_contributors"],
        "retained_items": support["retained_items"],
        "retained_positive_edges": support["retained_positive_edges"],
        "pair_contributions": pairs["pair_contributions"],
        "distinct_pairs": pairs["distinct_pairs"],
        "supported_pairs": pairs["supported_pairs"],
    }
    try:
        expected_bytes = canonical_json_bytes(fixture.expected_audit)
    except (TypeError, ValueError) as error:
        raise SnapshotAuditError(
            "fixture_invalid", "Fixture expected audit is not canonical JSON"
        ) from error
    if canonical_json_bytes(observed) != expected_bytes:
        raise SnapshotAuditError("fixture_expectation_mismatch", "Fixture audit drifted")
    report["fixture"] = {
        "fixture_id": fixture.fixture_id,
        "contract_fingerprint": fixture.contract_fingerprint,
        "provenance": "project-authored",
        "contains_real_user_data": False,
        "quality_evidence": False,
        "cold_start_empty_profile": True,
        "cold_start_unsupported_item": fixture.unsupported_game_slug,
    }
    return report
