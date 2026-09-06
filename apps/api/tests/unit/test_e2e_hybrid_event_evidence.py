import json
from pathlib import Path

import pytest

from tests.fixtures.e2e_fixture_stack import EventEvidence, _load_event_evidence


def _write_evidence(path: Path, *payloads: dict[str, object]) -> None:
    path.write_text(
        "".join(f"{json.dumps(payload)}\n" for payload in payloads),
        encoding="utf-8",
    )


def test_event_evidence_loads_bounded_exact_records(tmp_path: Path) -> None:
    _write_evidence(
        tmp_path / "chromium-0.jsonl",
        {
            "fallback_reason": None,
            "generation_id": "a" * 32,
            "ranking_mode": "hybrid",
        },
        {
            "fallback_reason": "artifact_missing",
            "generation_id": "b" * 32,
            "ranking_mode": "stage_4_fallback",
        },
    )

    assert _load_event_evidence(tmp_path) == (
        EventEvidence("a" * 32, "hybrid", None),
        EventEvidence("b" * 32, "stage_4_fallback", "artifact_missing"),
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "fallback_reason": None,
            "generation_id": "not-a-generation",
            "ranking_mode": "hybrid",
        },
        {
            "fallback_reason": None,
            "generation_id": "a" * 32,
            "ranking_mode": "unknown",
        },
        {
            "fallback_reason": "artifact_missing",
            "generation_id": "a" * 32,
            "ranking_mode": "hybrid",
        },
        {
            "fallback_reason": None,
            "generation_id": "a" * 32,
            "ranking_mode": "stage_4_fallback",
        },
        {
            "fallback_reason": None,
            "generation_id": "a" * 32,
            "ranking_mode": "hybrid",
            "extra": True,
        },
    ],
)
def test_event_evidence_rejects_invalid_records(tmp_path: Path, payload: dict[str, object]) -> None:
    _write_evidence(tmp_path / "chromium-0.jsonl", payload)

    with pytest.raises(RuntimeError, match="Browser event evidence"):
        _load_event_evidence(tmp_path)


def test_event_evidence_rejects_duplicate_generations_across_workers(tmp_path: Path) -> None:
    payload = {
        "fallback_reason": None,
        "generation_id": "a" * 32,
        "ranking_mode": "hybrid",
    }
    _write_evidence(tmp_path / "chromium-0.jsonl", payload)
    _write_evidence(tmp_path / "chromium-1.jsonl", payload)

    with pytest.raises(RuntimeError, match="duplicate generation"):
        _load_event_evidence(tmp_path)


def test_event_evidence_rejects_unexpected_members(tmp_path: Path) -> None:
    (tmp_path / "unexpected.txt").write_text("not evidence", encoding="utf-8")

    with pytest.raises(RuntimeError, match="invalid member"):
        _load_event_evidence(tmp_path)
