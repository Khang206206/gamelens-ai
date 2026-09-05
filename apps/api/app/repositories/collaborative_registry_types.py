from dataclasses import dataclass
from datetime import datetime
from typing import Literal

CollaborativeRegistryStatus = Literal["active", "invalidated", "retired"]


@dataclass(frozen=True, slots=True)
class CollaborativeReadinessRow:
    """One bounded database view of a live artifact's protected lineage."""

    build_id: str
    source_kind: Literal["fixture", "live"]
    status: CollaborativeRegistryStatus
    registered_revision: int
    invalidation_epoch: int
    contributor_count: int
    consent_version: str
    catalog_fingerprint: str
    interaction_fingerprint: str
    cutoff: datetime | None
    valid_until: datetime
