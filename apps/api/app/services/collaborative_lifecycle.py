from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import begin_read_committed
from app.repositories.collaborative_registry import (
    CollaborativeArtifactRegistryRepository,
    CollaborativeLifecycleTransition,
    CollaborativeRegistryMutationError,
)

CollaborativeLifecycleOperation = Literal["invalidate", "retire"]


class CollaborativeLifecycleError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CollaborativeLifecycleService:
    """Apply one deliberate, lock-serialized registry lifecycle transition."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def mutate(
        self,
        *,
        operation: CollaborativeLifecycleOperation,
        build_id: str,
    ) -> dict[str, object]:
        session = self.session_factory()
        try:
            begin_read_committed(session)
            repository = CollaborativeArtifactRegistryRepository(session)
            if operation == "invalidate":
                transition = repository.invalidate_live_build(build_id)
            elif operation == "retire":
                transition = repository.retire_live_build(build_id)
            else:
                raise CollaborativeLifecycleError(
                    "lifecycle_operation_invalid",
                    "Collaborative lifecycle operation is invalid",
                )
            session.commit()
        except (CollaborativeLifecycleError, CollaborativeRegistryMutationError):
            session.rollback()
            raise
        except SQLAlchemyError as error:
            session.rollback()
            raise CollaborativeLifecycleError(
                "lifecycle_database_failed",
                "PostgreSQL rejected the collaborative lifecycle transition",
            ) from error
        finally:
            session.close()
        return _transition_report(transition)


def _transition_report(transition: CollaborativeLifecycleTransition) -> dict[str, object]:
    return {
        "status": "ok",
        "operation": transition.operation,
        "build": {
            "id": transition.build_id,
            "previous_status": transition.previous_status,
            "status": transition.status,
            "changed": transition.changed,
            "invalidation_epoch": transition.invalidation_epoch,
            "effective_at": _format_timestamp(transition.effective_at),
        },
    }


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CollaborativeLifecycleError(
            "lifecycle_timestamp_invalid",
            "Collaborative lifecycle timestamp must be timezone-aware",
        )
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
