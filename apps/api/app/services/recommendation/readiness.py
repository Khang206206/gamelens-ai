from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from gamelens_recommender import LoadedCollaborativeArtifact

from app.services.recommendation.collaborative import (
    CollaborativeArtifactComponent,
    CollaborativeArtifactSourceKind,
    CollaborativeArtifactUnavailableReason,
)

CollaborativeReadinessState = Literal[
    "not_configured",
    "fixture_only",
    "insufficient_data",
    "unavailable",
    "stale",
    "ready",
]
CollaborativeReadinessReason = (
    CollaborativeArtifactUnavailableReason
    | Literal[
        "not_configured",
        "insufficient_data",
        "artifact_retired",
    ]
)
CollaborativeRegistryStatus = Literal["active", "invalidated", "retired"]

COLLABORATIVE_READINESS_REASONS: tuple[CollaborativeReadinessReason, ...] = (
    "not_configured",
    "fixture_not_allowed",
    "insufficient_data",
    "artifact_missing",
    "artifact_corrupt",
    "artifact_incompatible",
    "artifact_stale",
    "privacy_invalid",
    "artifact_expired",
    "catalog_stale",
    "artifact_retired",
)

_READINESS_STATES = frozenset(
    {"not_configured", "fixture_only", "insufficient_data", "unavailable", "stale", "ready"}
)
_DIRECT_UNAVAILABLE_REASONS = frozenset(
    {"fixture_not_allowed", "artifact_missing", "artifact_corrupt"}
)
_STALE_REASONS = frozenset(COLLABORATIVE_READINESS_REASONS) - {
    "not_configured",
    "insufficient_data",
    *_DIRECT_UNAVAILABLE_REASONS,
}
_LOWER_SHA256_LENGTH = 64
_MAX_BUILD_ID_LENGTH = 128
_MAX_CONSENT_VERSION_LENGTH = 100


@dataclass(frozen=True, slots=True)
class CollaborativeReadinessRow:
    """One bounded database view of a live artifact's protected lineage."""

    build_id: str
    source_kind: CollaborativeArtifactSourceKind
    status: CollaborativeRegistryStatus
    registered_revision: int
    invalidation_epoch: int
    contributor_count: int
    consent_version: str
    catalog_fingerprint: str
    interaction_fingerprint: str
    cutoff: datetime | None
    valid_until: datetime


@dataclass(frozen=True, slots=True)
class CollaborativeReadiness:
    """Serving decision for the optional component at one request snapshot."""

    state: CollaborativeReadinessState
    reason: CollaborativeReadinessReason | None
    source_kind: CollaborativeArtifactSourceKind | None
    artifact: LoadedCollaborativeArtifact | None = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            self.state not in _READINESS_STATES
            or (self.reason is not None and self.reason not in COLLABORATIVE_READINESS_REASONS)
            or self.source_kind not in {None, "fixture", "live"}
        ):
            raise ValueError("Collaborative readiness state is inconsistent")
        usable = self.state in {"fixture_only", "ready"}
        if usable:
            valid = (
                self.reason is None
                and self.source_kind in {"fixture", "live"}
                and self.artifact is not None
            )
            if self.state == "fixture_only":
                valid = valid and self.source_kind == "fixture"
            else:
                valid = valid and self.source_kind == "live"
        else:
            valid = self.reason is not None and self.artifact is None
            if self.state == "not_configured":
                valid = valid and self.reason == "not_configured" and self.source_kind is None
            elif self.state == "insufficient_data":
                valid = (
                    valid
                    and self.reason == "insufficient_data"
                    and self.source_kind in {"fixture", "live"}
                )
            elif self.state == "unavailable":
                valid = (
                    valid
                    and self.reason in _DIRECT_UNAVAILABLE_REASONS
                    and self.source_kind is None
                )
            elif self.state == "stale":
                valid = valid and self.reason in _STALE_REASONS
        if not valid:
            raise ValueError("Collaborative readiness state is inconsistent")

    @property
    def usable(self) -> bool:
        return self.state in {"fixture_only", "ready"}


@dataclass(frozen=True, slots=True)
class _ArtifactReadinessFacts:
    source_kind: CollaborativeArtifactSourceKind
    build_id: str
    data_revision: int | None
    contributor_count: int
    consent_version: str | None
    catalog_fingerprint: str
    interaction_fingerprint: str
    cutoff: datetime | None
    valid_until: datetime
    activation_minimum_users: int
    activation_minimum_edges: int
    activation_minimum_items: int
    retained_positive_edges: int
    retained_items: int


def _is_plain_int(value: object, *, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _LOWER_SHA256_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    normalized = parsed.astimezone(UTC)
    canonical = normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")
    return normalized if canonical == value else None


def _mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _artifact_facts(
    component: CollaborativeArtifactComponent,
) -> _ArtifactReadinessFacts | None:
    artifact = component.artifact
    if artifact is None or component.source_kind is None:
        return None
    try:
        manifest = _mapping(artifact.manifest)
        if manifest is None:
            return None
        source = _mapping(manifest.get("source"))
        build = _mapping(manifest.get("build"))
        lifecycle = _mapping(manifest.get("lifecycle"))
        matrix = _mapping(manifest.get("matrix"))
        thresholds = _mapping(manifest.get("thresholds"))
        if any(value is None for value in (source, build, lifecycle, matrix, thresholds)):
            return None

        raw_source_kind = source.get("kind")
        build_id = build.get("id")
        data_revision = lifecycle.get("data_revision")
        consent_version = lifecycle.get("consent_version")
        cutoff = _parse_timestamp(lifecycle.get("cutoff"))
        valid_until = _parse_timestamp(lifecycle.get("valid_until"))
        contributor_count = matrix.get("retained_contributors")
        retained_positive_edges = matrix.get("retained_positive_edges")
        retained_items = matrix.get("retained_items")
        activation_minimum_users = thresholds.get("activation_minimum_users")
        activation_minimum_edges = thresholds.get("activation_minimum_edges")
        activation_minimum_items = thresholds.get("activation_minimum_items")
        catalog_fingerprint = manifest.get("catalog_fingerprint")
        interaction_fingerprint = manifest.get("interaction_fingerprint")

        if (
            raw_source_kind not in {"fixture", "live"}
            or raw_source_kind != component.source_kind
            or not isinstance(build_id, str)
            or not 1 <= len(build_id) <= _MAX_BUILD_ID_LENGTH
            or not _is_plain_int(contributor_count)
            or not _is_plain_int(retained_positive_edges)
            or not _is_plain_int(retained_items)
            or not _is_plain_int(activation_minimum_users, minimum=1)
            or not _is_plain_int(activation_minimum_edges, minimum=1)
            or not _is_plain_int(activation_minimum_items, minimum=1)
            or not _is_sha256(catalog_fingerprint)
            or not _is_sha256(interaction_fingerprint)
            or valid_until is None
        ):
            return None
        if raw_source_kind == "fixture":
            if data_revision is not None or consent_version is not None or cutoff is not None:
                return None
        elif (
            not _is_plain_int(data_revision)
            or not isinstance(consent_version, str)
            or not consent_version
            or consent_version != consent_version.strip()
            or len(consent_version) > _MAX_CONSENT_VERSION_LENGTH
            or cutoff is None
        ):
            return None

        return _ArtifactReadinessFacts(
            source_kind=raw_source_kind,
            build_id=build_id,
            data_revision=data_revision,
            contributor_count=contributor_count,
            consent_version=consent_version,
            catalog_fingerprint=catalog_fingerprint,
            interaction_fingerprint=interaction_fingerprint,
            cutoff=cutoff,
            valid_until=valid_until,
            activation_minimum_users=activation_minimum_users,
            activation_minimum_edges=activation_minimum_edges,
            activation_minimum_items=activation_minimum_items,
            retained_positive_edges=retained_positive_edges,
            retained_items=retained_items,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def collaborative_readiness_build_id(
    component: CollaborativeArtifactComponent,
) -> str | None:
    """Return the validated live build identity needed for one registry lookup."""

    facts = _artifact_facts(component)
    return facts.build_id if facts is not None and facts.source_kind == "live" else None


def _unusable(
    state: CollaborativeReadinessState,
    reason: CollaborativeReadinessReason,
    *,
    source_kind: CollaborativeArtifactSourceKind | None = None,
) -> CollaborativeReadiness:
    return CollaborativeReadiness(
        state=state,
        reason=reason,
        source_kind=source_kind,
        artifact=None,
    )


def _loaded_component_failure(
    component: CollaborativeArtifactComponent,
) -> CollaborativeReadiness | None:
    if component.load_state == "not_configured":
        return _unusable("not_configured", "not_configured")
    if component.load_state == "loaded":
        return None
    reason = component.unavailable_reason or "artifact_incompatible"
    state: CollaborativeReadinessState = (
        "unavailable" if reason in _DIRECT_UNAVAILABLE_REASONS else "stale"
    )
    return _unusable(state, reason)


def _lineage_is_well_formed(row: CollaborativeReadinessRow) -> bool:
    return (
        isinstance(row, CollaborativeReadinessRow)
        and isinstance(row.build_id, str)
        and 1 <= len(row.build_id) <= _MAX_BUILD_ID_LENGTH
        and row.source_kind == "live"
        and row.status in {"active", "invalidated", "retired"}
        and _is_plain_int(row.registered_revision)
        and _is_plain_int(row.invalidation_epoch)
        and _is_plain_int(row.contributor_count)
        and isinstance(row.consent_version, str)
        and bool(row.consent_version)
        and row.consent_version == row.consent_version.strip()
        and len(row.consent_version) <= _MAX_CONSENT_VERSION_LENGTH
        and _is_sha256(row.catalog_fingerprint)
        and _is_sha256(row.interaction_fingerprint)
        and isinstance(row.cutoff, datetime)
        and row.cutoff.tzinfo is not None
        and row.cutoff.utcoffset() is not None
        and isinstance(row.valid_until, datetime)
        and row.valid_until.tzinfo is not None
        and row.valid_until.utcoffset() is not None
    )


def evaluate_collaborative_readiness(
    component: CollaborativeArtifactComponent,
    *,
    catalog_fingerprint: str,
    current_consent_version: str | None,
    now: datetime,
    lineage: CollaborativeReadinessRow | None = None,
) -> CollaborativeReadiness:
    """Evaluate optional serving readiness without I/O or mutable state.

    A caller supplies database time and at most one live-lineage row from its
    request transaction. New post-cutoff positives deliberately do not enter
    this contract; targeted invalidation is represented by the row status and
    epoch instead.
    """

    intrinsic_failure = _loaded_component_failure(component)
    if intrinsic_failure is not None:
        return intrinsic_failure

    facts = _artifact_facts(component)
    if facts is None:
        return _unusable(
            "stale",
            "artifact_incompatible",
            source_kind=component.source_kind,
        )
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return _unusable("stale", "artifact_incompatible", source_kind=facts.source_kind)
    current_time = now.astimezone(UTC)
    if current_time >= facts.valid_until:
        return _unusable("stale", "artifact_expired", source_kind=facts.source_kind)
    if not _is_sha256(catalog_fingerprint) or catalog_fingerprint != facts.catalog_fingerprint:
        return _unusable("stale", "catalog_stale", source_kind=facts.source_kind)
    if (
        facts.contributor_count < facts.activation_minimum_users
        or facts.retained_positive_edges < facts.activation_minimum_edges
        or facts.retained_items < facts.activation_minimum_items
    ):
        return _unusable(
            "insufficient_data",
            "insufficient_data",
            source_kind=facts.source_kind,
        )

    artifact = component.artifact
    if artifact is None:
        return _unusable("stale", "artifact_incompatible", source_kind=facts.source_kind)
    if facts.source_kind == "fixture":
        return CollaborativeReadiness(
            state="fixture_only",
            reason=None,
            source_kind="fixture",
            artifact=artifact,
        )

    if lineage is None or not _lineage_is_well_formed(lineage):
        return _unusable("stale", "privacy_invalid", source_kind="live")
    if lineage.status == "retired":
        return _unusable("stale", "artifact_retired", source_kind="live")
    if lineage.status != "active" or lineage.invalidation_epoch != 0:
        return _unusable("stale", "privacy_invalid", source_kind="live")
    if lineage.build_id != facts.build_id or lineage.registered_revision != facts.data_revision:
        return _unusable("stale", "artifact_stale", source_kind="live")
    if facts.cutoff is None or lineage.cutoff is None:
        return _unusable("stale", "privacy_invalid", source_kind="live")
    if lineage.cutoff.astimezone(UTC) != facts.cutoff:
        return _unusable("stale", "artifact_stale", source_kind="live")
    if (
        lineage.contributor_count != facts.contributor_count
        or lineage.interaction_fingerprint != facts.interaction_fingerprint
    ):
        return _unusable("stale", "privacy_invalid", source_kind="live")
    if (
        current_consent_version is None
        or current_consent_version != facts.consent_version
        or lineage.consent_version != facts.consent_version
    ):
        return _unusable("stale", "privacy_invalid", source_kind="live")
    if (
        lineage.catalog_fingerprint != facts.catalog_fingerprint
        or lineage.catalog_fingerprint != catalog_fingerprint
    ):
        return _unusable("stale", "catalog_stale", source_kind="live")
    lineage_valid_until = lineage.valid_until.astimezone(UTC)
    if lineage_valid_until != facts.valid_until:
        return _unusable("stale", "artifact_stale", source_kind="live")
    if current_time >= lineage_valid_until:
        return _unusable("stale", "artifact_expired", source_kind="live")

    return CollaborativeReadiness(
        state="ready",
        reason=None,
        source_kind="live",
        artifact=artifact,
    )
