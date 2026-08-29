import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from gamelens_recommender import (
    CollaborativeArtifactError,
    LoadedCollaborativeArtifact,
    load_collaborative_artifact,
)

logger = logging.getLogger(__name__)

CollaborativeArtifactLoadState = Literal["not_configured", "loaded", "unavailable"]
CollaborativeArtifactSourceKind = Literal["fixture", "live"]
CollaborativeArtifactUnavailableReason = Literal[
    "fixture_not_allowed",
    "artifact_missing",
    "artifact_corrupt",
    "artifact_incompatible",
    "artifact_stale",
    "privacy_invalid",
    "artifact_expired",
    "catalog_stale",
]

_CORRUPT_ARTIFACT_CODES = frozenset(
    {
        "manifest_invalid",
        "artifact_limit_exceeded",
        "artifact_path_invalid",
        "artifact_format_invalid",
        "artifact_shape_invalid",
        "artifact_dtype_invalid",
        "artifact_numeric_invalid",
        "artifact_integrity_failed",
    }
)
_INCOMPATIBLE_ARTIFACT_CODES = frozenset(
    {
        "artifact_schema_incompatible",
        "model_incompatible",
        "code_incompatible",
        "config_incompatible",
    }
)


@dataclass(frozen=True, slots=True)
class CollaborativeArtifactComponent:
    """Immutable intrinsic state for the optional collaborative artifact.

    Database-backed lifecycle readiness is intentionally outside this type. A
    loaded live artifact is only structurally available until a later serving
    boundary validates its protected registry lineage.
    """

    load_state: CollaborativeArtifactLoadState
    source_kind: CollaborativeArtifactSourceKind | None
    unavailable_reason: CollaborativeArtifactUnavailableReason | None
    artifact: LoadedCollaborativeArtifact | None = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.load_state == "not_configured":
            valid = (
                self.source_kind is None
                and self.unavailable_reason is None
                and self.artifact is None
            )
        elif self.load_state == "unavailable":
            valid = (
                self.source_kind is None
                and self.unavailable_reason is not None
                and self.artifact is None
            )
        else:
            valid = (
                self.source_kind in {"fixture", "live"}
                and self.unavailable_reason is None
                and self.artifact is not None
            )
        if not valid:
            raise ValueError("Collaborative artifact component state is inconsistent")

    @classmethod
    def not_configured(cls) -> "CollaborativeArtifactComponent":
        return cls(
            load_state="not_configured",
            source_kind=None,
            unavailable_reason=None,
            artifact=None,
        )

    @classmethod
    def unavailable(
        cls,
        reason: CollaborativeArtifactUnavailableReason,
    ) -> "CollaborativeArtifactComponent":
        return cls(
            load_state="unavailable",
            source_kind=None,
            unavailable_reason=reason,
            artifact=None,
        )

    @classmethod
    def loaded(
        cls,
        artifact: LoadedCollaborativeArtifact,
        *,
        source_kind: CollaborativeArtifactSourceKind,
    ) -> "CollaborativeArtifactComponent":
        return cls(
            load_state="loaded",
            source_kind=source_kind,
            unavailable_reason=None,
            artifact=artifact,
        )


def _normalized_artifact_reason(code: str) -> CollaborativeArtifactUnavailableReason:
    if code == "fixture_not_allowed":
        return "fixture_not_allowed"
    if code == "artifact_missing":
        return "artifact_missing"
    if code == "artifact_expired":
        return "artifact_expired"
    if code == "catalog_mismatch":
        return "catalog_stale"
    if code in {"artifact_stale_revision", "revision_race"}:
        return "artifact_stale"
    if code == "consent_policy_incompatible":
        return "privacy_invalid"
    if code in _CORRUPT_ARTIFACT_CODES:
        return "artifact_corrupt"
    if code in _INCOMPATIBLE_ARTIFACT_CODES:
        return "artifact_incompatible"
    return "artifact_incompatible"


def _unavailable(
    reason: CollaborativeArtifactUnavailableReason,
    error: BaseException,
) -> CollaborativeArtifactComponent:
    logger.warning(
        "Collaborative artifact component is unavailable",
        extra={"reason": reason, "error_type": type(error).__name__},
    )
    return CollaborativeArtifactComponent.unavailable(reason)


def create_collaborative_component(
    path: Path | None,
    *,
    environment: Literal["development", "test", "production"],
    allow_test_fixture: bool,
) -> CollaborativeArtifactComponent:
    """Load one optional bundle once without affecting required content serving."""

    if path is None:
        return CollaborativeArtifactComponent.not_configured()

    allow_fixture = environment == "test" and allow_test_fixture
    try:
        artifact = load_collaborative_artifact(path, allow_fixture=allow_fixture)
        raw_source_kind = artifact.manifest["source"]["kind"]
        if raw_source_kind not in {"fixture", "live"}:
            raise ValueError("Loaded collaborative artifact source kind is invalid")
        source_kind: CollaborativeArtifactSourceKind = raw_source_kind
        return CollaborativeArtifactComponent.loaded(artifact, source_kind=source_kind)
    except CollaborativeArtifactError as error:
        return _unavailable(_normalized_artifact_reason(error.code), error)
    except OSError as error:
        return _unavailable("artifact_missing", error)
    except (KeyError, TypeError, ValueError) as error:
        return _unavailable("artifact_corrupt", error)
    except Exception as error:
        return _unavailable("artifact_incompatible", error)
