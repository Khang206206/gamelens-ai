from __future__ import annotations

from collections.abc import Callable

from gamelens_recommender import audit_profiles
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.collaborative_snapshot import (
    CollaborativeSnapshotRepository,
    begin_collaborative_snapshot,
    verify_data_revision,
)


def blocked_live_audit(
    *,
    live_data_enabled: bool = False,
    contribution_consent_version_configured: bool = False,
) -> dict[str, object]:
    return {
        "audit_schema_version": 1,
        "source_kind": "live",
        "status": "integration_blocked",
        "ready_for_functional_build": False,
        "approved_live_training_eligibility": False,
        "reasons": ["unapproved_live_source"],
        "privacy": {
            "aggregate_only": True,
            "user_identifiers_emitted": False,
            "row_level_snapshot_written": False,
            "cohort_mapping_written": False,
        },
        "integration_gates": {
            "live_data_enabled": live_data_enabled,
            "contribution_consent_version_configured": contribution_consent_version_configured,
            "build_lineage_implemented": False,
            "serving_activation_approved": False,
        },
    }


def audit_live_snapshot(
    session_factory: Callable[[], Session],
    *,
    settings: Settings,
) -> dict[str, object]:
    contribution_version = settings.collaborative_contribution_consent_version
    if not settings.collaborative_live_data_enabled or contribution_version is None:
        return blocked_live_audit(
            live_data_enabled=settings.collaborative_live_data_enabled,
            contribution_consent_version_configured=contribution_version is not None,
        )

    session = session_factory()
    try:
        begin_collaborative_snapshot(session)
        snapshot = CollaborativeSnapshotRepository(session).extract(
            personalization_consent_version=settings.consent_version,
            contribution_consent_version=contribution_version,
        )
    finally:
        session.rollback()
        session.close()

    verifier = session_factory()
    try:
        verify_data_revision(verifier, expected_revision=snapshot.data_revision)
    finally:
        verifier.rollback()
        verifier.close()

    report = audit_profiles(
        snapshot.profiles,
        source_kind="live",
        catalog_fingerprint=snapshot.catalog_fingerprint,
        exclusion_counts=snapshot.exclusion_counts,
        cutoff=snapshot.cutoff.isoformat(),
        data_revision=snapshot.data_revision,
        consent_version=contribution_version,
    )
    report["integration_gates"] = {
        "live_data_enabled": True,
        "contribution_consent_version_configured": True,
        "build_lineage_implemented": False,
        "serving_activation_approved": False,
    }
    return report
