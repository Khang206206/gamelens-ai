from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from gamelens_recommender import ucsd_steam
from gamelens_recommender.ucsd_steam import (
    BLOCKING_REASONS,
    EXPECTED_GATE_STATES,
    SOURCE_FORMAT,
    SOURCE_STATUS,
    SourceAuditError,
    _source_suitability,
    audit_source,
    canonical_json_bytes,
    main,
    prepare_source,
    verify_source,
)

SOURCE_DEFINITIONS = (
    (
        "v1-user-items",
        "data/raw/ucsd-steam/v1-user-items/australian_users_items.json.gz",
        "https://mcauleylab.ucsd.edu/public_datasets/data/steam/australian_users_items.json.gz",
    ),
    (
        "v1-reviews",
        "data/raw/ucsd-steam/v1-reviews/australian_user_reviews.json.gz",
        "https://mcauleylab.ucsd.edu/public_datasets/data/steam/australian_user_reviews.json.gz",
    ),
    (
        "v2-item-metadata",
        "data/raw/ucsd-steam/v2-item-metadata/steam_games.json.gz",
        "https://cseweb.ucsd.edu/~wckang/steam_games.json.gz",
    ),
)
ITEM_IDS = ("10", "20", "30", "40", "50")


def _gzip_bytes(lines: list[bytes]) -> bytes:
    import io

    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as stream:
        for line in lines:
            stream.write(line)
    return buffer.getvalue()


def _literal_lines(records: list[dict[str, object]]) -> list[bytes]:
    return [(repr(record) + "\n").encode("utf-8") for record in records]


def _records(*, user_prefix: str, reverse_reviews: bool = False) -> dict[str, list[bytes]]:
    user_items = [
        {
            "user_id": f"{user_prefix}-0",
            "user_url": "https://example.invalid/private-profile",
            "steam_id": "private-steam-identity",
            "items_count": 2,
            "items": [
                {"item_id": "10", "playtime_forever": 120},
                {"item_id": "999", "playtime_forever": 0},
            ],
        }
    ]
    reviews: list[dict[str, object]] = []
    for index in range(10):
        user_id = f"{user_prefix}-{index}"
        values = [
            {"item_id": item_id, "recommend": True, "review": "fixture"} for item_id in ITEM_IDS
        ]
        if index == 0:
            reviews.append({"user_id": user_id, "reviews": values[:2]})
            reviews.append(
                {
                    "user_id": user_id,
                    "reviews": [
                        *values[2:],
                        {"item_id": "999", "recommend": False, "review": "fixture"},
                    ],
                }
            )
        else:
            reviews.append({"user_id": user_id, "reviews": values})
    if reverse_reviews:
        reviews.reverse()
    metadata = [
        {"id": item_id, "title": f"Fixture {item_id}", "app_name": f"Fixture {item_id}"}
        for item_id in ITEM_IDS
    ]
    return {
        "v1-user-items": _literal_lines(user_items),
        "v1-reviews": _literal_lines(reviews),
        "v2-item-metadata": _literal_lines(metadata),
    }


def _write_source_tree(
    root: Path,
    *,
    user_prefix: str = "sensitive-user",
    reverse_reviews: bool = False,
    metadata_duplicate: bool = False,
) -> Path:
    lines_by_role = _records(user_prefix=user_prefix, reverse_reviews=reverse_reviews)
    if metadata_duplicate:
        lines_by_role["v2-item-metadata"].append(
            repr({"id": "10", "title": "Ambiguous duplicate"}).encode("utf-8") + b"\n"
        )
    files: list[dict[str, object]] = []
    for role, relative_path, source_url in SOURCE_DEFINITIONS:
        lines = lines_by_role[role]
        payload = _gzip_bytes(lines)
        path = root / Path(*relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        files.append(
            {
                "role": role,
                "relative_path": relative_path,
                "source_url": source_url,
                "compressed_size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "uncompressed_size_bytes": sum(map(len, lines)),
                "line_count": len(lines),
                "max_line_bytes": max(map(len, lines)),
            }
        )
    manifest = {
        "manifest_schema_version": 1,
        "dataset": "ucsd-steam",
        "source_attribution": "UCSD McAuley Lab",
        "retrieved_on": "2026-08-19",
        "status": SOURCE_STATUS,
        "source_format": SOURCE_FORMAT,
        "dataset_page": "https://cseweb.ucsd.edu/~jmcauley/datasets.html",
        "raw_transformations": [],
        "redistribution_status": "not-assessed-do-not-redistribute",
        "citation_requested": True,
        "integration_gates": EXPECTED_GATE_STATES,
        "files": files,
    }
    manifest_path = root / "data/manifests/ucsd-steam/source-v1.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _rewrite_manifest_entry(root: Path, role: str, lines: list[bytes]) -> None:
    manifest_path = root / "data/manifests/ucsd-steam/source-v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(item for item in manifest["files"] if item["role"] == role)
    payload = _gzip_bytes(lines)
    source_path = root / Path(*entry["relative_path"].split("/"))
    source_path.write_bytes(payload)
    entry.update(
        {
            "compressed_size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "uncompressed_size_bytes": sum(map(len, lines)),
            "line_count": len(lines),
            "max_line_bytes": max(map(len, lines)),
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_all_workflows_are_read_only_and_keep_integration_blocked(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)
    source_paths = [
        tmp_path / Path(*relative_path.split("/")) for _, relative_path, _ in SOURCE_DEFINITIONS
    ]
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in source_paths]

    report = verify_source(tmp_path)
    prepare_source(tmp_path)
    audit_source(tmp_path)

    assert report["status"] == "verified_not_integrated"
    assert report["integration"]["integration_ready"] is False
    assert report["integration"]["blocking_reasons"] == list(BLOCKING_REASONS)
    assert report["verification"]["status"] == "passed"
    assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in source_paths] == before


def test_all_checksums_are_checked_before_any_literal_is_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source_tree(tmp_path)
    path = tmp_path / Path(*SOURCE_DEFINITIONS[-1][1].split("/"))
    payload = bytearray(path.read_bytes())
    payload[len(payload) // 2] ^= 1
    path.write_bytes(payload)
    monkeypatch.setattr(
        ucsd_steam,
        "_parse_record",
        lambda *args, **kwargs: pytest.fail("literal parser ran before all checksum gates"),
    )

    with pytest.raises(SourceAuditError) as raised:
        prepare_source(tmp_path)

    assert raised.value.code == "source_checksum_mismatch"


def test_safe_literal_parser_never_executes_source_text(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)
    malicious = b"{'user_id': __import__('pathlib').Path('owned').write_text('x'), 'reviews': []}\n"
    _rewrite_manifest_entry(tmp_path, "v1-reviews", [malicious])

    with pytest.raises(SourceAuditError) as raised:
        prepare_source(tmp_path)

    assert raised.value.code == "source_parse_invalid"
    assert not (tmp_path / "owned").exists()


def test_safe_literal_type_error_is_typed(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)
    _rewrite_manifest_entry(tmp_path, "v1-reviews", [b"{[]}\n"])

    with pytest.raises(SourceAuditError) as raised:
        prepare_source(tmp_path)

    assert raised.value.code == "source_parse_invalid"


def test_prepare_merges_duplicate_user_records_and_emits_only_aggregates(
    tmp_path: Path,
) -> None:
    _write_source_tree(tmp_path)

    report = prepare_source(tmp_path)

    reviews = report["preparation"]["source_profiles"]["v1_reviews"]
    user_items = report["preparation"]["source_profiles"]["v1_user_items"]
    assert reviews["records"] == 11
    assert reviews["distinct_users"] == 10
    assert reviews["duplicate_user_records"] == 1
    assert reviews["candidate_recommend_true_pairs"] == 50
    assert reviews["false_only_pairs_excluded_from_candidates"] == 1
    assert user_items["positive_playtime_rows_excluded_from_candidates"] == 1
    assert report["preparation"]["target_catalog_join"] == {
        "status": "not_attempted-no-mapping-artifact",
        "mapped_candidate_pairs": 0,
        "mapped_candidate_items": 0,
    }
    serialized = json.dumps(report, sort_keys=True)
    assert "sensitive-user" not in serialized
    assert '"user_id"' not in serialized
    assert "private-profile" not in serialized
    assert "private-steam-identity" not in serialized
    assert '"user_url"' not in serialized
    assert '"steam_id"' not in serialized


def test_prepare_collapses_same_flag_duplicates_and_excludes_conflicts(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)
    reviews = [
        {
            "user_id": "duplicate-policy-user",
            "reviews": [
                {"item_id": "10", "recommend": True},
                {"item_id": "10", "recommend": True},
                {"item_id": "20", "recommend": True},
                {"item_id": "20", "recommend": False},
                {"item_id": "30", "recommend": True},
            ],
        }
    ]
    _rewrite_manifest_entry(tmp_path, "v1-reviews", _literal_lines(reviews))

    prepared = prepare_source(tmp_path)
    profile = prepared["preparation"]["source_profiles"]["v1_reviews"]
    alignment = prepared["preparation"]["source_metadata_alignment"]

    assert profile["review_rows"] == 5
    assert profile["unique_user_item_pairs"] == 3
    assert profile["duplicate_pair_rows"] == 2
    assert profile["conflicting_recommend_pairs_excluded"] == 1
    assert profile["candidate_recommend_true_pairs"] == 2
    assert profile["false_only_pairs_excluded_from_candidates"] == 0
    assert alignment["candidate_positive_pairs"] == {"matched": 2, "total": 2, "rate": 1.0}

    audited = audit_source(tmp_path)
    candidates = audited["suitability"]["candidate_profiles"]
    assert candidates["users_with_candidate_positive"] == 1
    assert candidates["candidate_positive_edges"] == 2
    assert candidates["distinct_candidate_items"] == 2


def test_profile_fingerprint_ignores_row_order_and_user_identifier_allocation(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_source_tree(first, user_prefix="first-user")
    _write_source_tree(second, user_prefix="second-user", reverse_reviews=True)

    first_report = audit_source(first)
    second_report = audit_source(second)

    assert (
        first_report["suitability"]["candidate_profile_fingerprint"]
        == second_report["suitability"]["candidate_profile_fingerprint"]
    )
    assert (
        first_report["suitability"]["support_filter"]
        == second_report["suitability"]["support_filter"]
    )
    assert (
        first_report["suitability"]["pair_support"] == second_report["suitability"]["pair_support"]
    )


def test_source_support_does_not_open_integration_gate(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)

    report = audit_source(tmp_path)

    assert report["suitability"]["source_level_support_passes"] is True
    assert report["suitability"]["ready_for_functional_build"] is False
    assert report["suitability"]["approved_training_eligibility"] is False
    assert report["integration"]["integration_ready"] is False
    assert report["suitability"]["support_filter"] == {
        "algorithm": "deterministic-queue-bipartite-two-core-v1",
        "multi_positive_users_before_item_support": 10,
        "positive_edges_before_item_support": 50,
        "distinct_items_before_item_support": 5,
        "fixed_point_passes": 1,
        "retained_items": 5,
        "retained_users": 10,
        "retained_positive_edges": 50,
        "matrix_density": {"numerator": 50, "denominator": 50, "rate": 1.0},
        "item_support_distribution_before_filter": {
            "0": 0,
            "1": 0,
            "2": 0,
            "3-4": 0,
            "5-9": 0,
            "10+": 5,
        },
        "item_support_distribution_after_filter": {
            "0": 0,
            "1": 0,
            "2": 0,
            "3-4": 0,
            "5-9": 0,
            "10+": 5,
        },
    }


def test_ambiguous_metadata_id_is_excluded_from_source_alignment(tmp_path: Path) -> None:
    _write_source_tree(tmp_path, metadata_duplicate=True)

    report = prepare_source(tmp_path)

    metadata = report["preparation"]["source_profiles"]["v2_item_metadata"]
    alignment = report["preparation"]["source_metadata_alignment"]
    assert metadata["ambiguous_item_ids_excluded_from_alignment"] == 1
    assert metadata["unambiguous_item_ids"] == 4
    assert alignment["candidate_positive_pairs"] == {
        "matched": 40,
        "total": 50,
        "rate": 0.8,
    }


def test_structural_insufficiency_is_typed_without_becoming_an_error(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)
    one_profile = [
        repr(
            {
                "user_id": "one-user",
                "reviews": [{"item_id": "10", "recommend": True}],
            }
        ).encode("utf-8")
        + b"\n"
    ]
    _rewrite_manifest_entry(tmp_path, "v1-reviews", one_profile)

    report = audit_source(tmp_path)

    assert report["status"] == "source_support_measured_integration_blocked"
    assert report["suitability"]["source_level_support_passes"] is False
    assert report["suitability"]["source_level_reasons"] == [
        "no_multi_positive_users",
        "no_supported_items",
        "no_supported_pairs",
        "insufficient_activation_users",
        "insufficient_activation_edges",
        "insufficient_activation_items",
    ]


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            lambda manifest: manifest["integration_gates"].update(
                {"license_and_redistribution": "approved"}
            ),
            "manifest_invalid",
        ),
        (
            lambda manifest: manifest["files"][0].update({"relative_path": "../outside.json.gz"}),
            "manifest_invalid",
        ),
        (
            lambda manifest: manifest.update({"retrieved_on": "2026-08-18"}),
            "manifest_invalid",
        ),
        (
            lambda manifest: manifest["files"][0].update(
                {"source_url": "https://mcauleylab.ucsd.edu/not-the-frozen-source.json.gz"}
            ),
            "manifest_invalid",
        ),
        (
            lambda manifest: manifest.update({"dataset_page": "https://["}),
            "manifest_invalid",
        ),
        (
            lambda manifest: manifest.update({"raw_transformations": ["decompressed"]}),
            "manifest_invalid",
        ),
        (
            lambda manifest: manifest.update({"manifest_schema_version": True}),
            "manifest_schema_incompatible",
        ),
    ],
)
def test_manifest_fails_closed_on_open_gate_or_unsafe_path(
    tmp_path: Path,
    mutation,
    expected_code: str,
) -> None:
    manifest_path = _write_source_tree(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutation(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SourceAuditError) as raised:
        verify_source(tmp_path)

    assert raised.value.code == expected_code


def test_cli_returns_success_for_expected_blocked_state_and_emits_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_source_tree(tmp_path)

    exit_code = main(["audit", "--root", str(tmp_path), "--format", "json"])

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "source_support_measured_integration_blocked"
    assert report["integration"]["integration_ready"] is False


def test_support_filter_prunes_users_and_items_to_a_fixed_point() -> None:
    report = _source_suitability(
        (
            ("10", "20"),
            ("10", "30"),
            ("30", "40"),
        )
    )

    support = report["support_filter"]
    assert support["fixed_point_passes"] == 3
    assert support["retained_users"] == 0
    assert support["retained_items"] == 0
    assert support["retained_positive_edges"] == 0
    assert support["item_support_distribution_after_filter"] == {
        "0": 0,
        "1": 0,
        "2": 0,
        "3-4": 0,
        "5-9": 0,
        "10+": 0,
    }
    assert report["pair_support"]["distinct_pairs"] == 0


def test_queue_support_filter_handles_a_long_peeling_chain() -> None:
    profiles = tuple((str(index), str(index + 1)) for index in range(2_000))

    report = _source_suitability(profiles)
    support = report["support_filter"]

    assert support["algorithm"] == "deterministic-queue-bipartite-two-core-v1"
    assert support["fixed_point_passes"] == 1_001
    assert support["retained_positive_edges"] == 0


def test_source_symlink_is_rejected_before_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source_tree(tmp_path)
    source_path = tmp_path / Path(*SOURCE_DEFINITIONS[0][1].split("/"))
    target_path = tmp_path / "source-link-target.json.gz"
    source_path.replace(target_path)
    try:
        source_path.symlink_to(target_path)
    except (NotImplementedError, OSError):
        monkeypatch.setattr(Path, "is_symlink", lambda candidate: candidate == source_path)

    with pytest.raises(SourceAuditError) as raised:
        verify_source(tmp_path)

    assert raised.value.code == "source_path_invalid"


def test_post_parse_checksum_detects_same_size_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source_tree(tmp_path)
    source_path = tmp_path / Path(*SOURCE_DEFINITIONS[0][1].split("/"))
    original_profiles_from_pairs = ucsd_steam._profiles_from_pairs

    def mutate_after_parse(pair_states, metadata_item_ids):
        result = original_profiles_from_pairs(pair_states, metadata_item_ids)
        payload = bytearray(source_path.read_bytes())
        payload[len(payload) // 2] ^= 1
        source_path.write_bytes(payload)
        return result

    monkeypatch.setattr(ucsd_steam, "_profiles_from_pairs", mutate_after_parse)

    with pytest.raises(SourceAuditError) as raised:
        prepare_source(tmp_path)

    assert raised.value.code == "source_checksum_mismatch"


def test_bounded_hash_rejects_bytes_appended_after_the_size_check(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)
    manifest = ucsd_steam.load_manifest(tmp_path, "data/manifests/ucsd-steam/source-v1.json")
    source = manifest.files[0]
    source_path = tmp_path / Path(*source.relative_path.split("/"))
    source_path.write_bytes(source_path.read_bytes() + b"unexpected")

    with pytest.raises(SourceAuditError) as raised:
        ucsd_steam._sha256_file(source_path, source)

    assert raised.value.code == "source_size_mismatch"


def test_deflate_error_is_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_source_tree(tmp_path)

    class CorruptGzipStream:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def readline(self, _maximum_bytes: int) -> bytes:
            raise ucsd_steam.zlib.error("corrupt DEFLATE stream")

    monkeypatch.setattr(ucsd_steam.gzip, "open", lambda *_args, **_kwargs: CorruptGzipStream())

    with pytest.raises(SourceAuditError) as raised:
        verify_source(tmp_path)

    assert raised.value.code == "source_gzip_invalid"


def test_truncated_gzip_with_updated_compressed_identity_is_rejected(tmp_path: Path) -> None:
    manifest_path = _write_source_tree(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest["files"][-1]
    source_path = tmp_path / Path(*entry["relative_path"].split("/"))
    payload = source_path.read_bytes()[:-8]
    source_path.write_bytes(payload)
    entry["compressed_size_bytes"] = len(payload)
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SourceAuditError) as raised:
        verify_source(tmp_path)

    assert raised.value.code == "source_gzip_invalid"


def test_gzip_shape_mismatch_is_typed(tmp_path: Path) -> None:
    manifest_path = _write_source_tree(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["line_count"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SourceAuditError) as raised:
        verify_source(tmp_path)

    assert raised.value.code == "source_shape_mismatch"


def test_nonfinite_playtime_is_invalid_and_never_a_candidate(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)
    lines = [
        (
            b"{'user_id': 'finite-check', 'items_count': 1, "
            b"'items': [{'item_id': '10', 'playtime_forever': 1e999}]}\n"
        )
    ]
    _rewrite_manifest_entry(tmp_path, "v1-user-items", lines)

    report = prepare_source(tmp_path)
    user_items = report["preparation"]["source_profiles"]["v1_user_items"]

    assert user_items["invalid_playtime_rows"] == 1
    assert user_items["positive_playtime_rows_excluded_from_candidates"] == 0


@pytest.mark.parametrize(
    ("malformed_kind", "output_format"),
    [
        ("nonfinite", "json"),
        ("overflow", "summary"),
        ("duplicate-key", "summary"),
        ("surrogate", "json"),
    ],
)
def test_cli_manifest_errors_are_typed_in_json_and_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    malformed_kind: str,
    output_format: str,
) -> None:
    manifest_path = _write_source_tree(tmp_path)
    text = manifest_path.read_text(encoding="utf-8")
    if malformed_kind == "nonfinite":
        text = text.replace("{", '{"unexpected": NaN,', 1)
    elif malformed_kind == "overflow":
        text = text.replace("{", '{"unexpected": 1e999,', 1)
    elif malformed_kind == "duplicate-key":
        text = text.replace(
            '"dataset": "ucsd-steam",',
            '"dataset": "ucsd-steam", "dataset": "ucsd-steam",',
            1,
        )
    else:
        text = text.replace("{", '{"unexpected": "\\ud800",', 1)
    manifest_path.write_text(text, encoding="utf-8")

    exit_code = main(["verify", "--root", str(tmp_path), "--format", output_format])

    assert exit_code == 2
    output = capsys.readouterr().out
    if output_format == "json":
        assert json.loads(output)["error"]["code"] == "manifest_invalid"
    else:
        assert "Error: manifest_invalid:" in output


def test_cli_can_check_a_committed_report_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_source_tree(tmp_path)
    expected = audit_source(tmp_path)
    relative_report = "data/audits/ucsd-steam/expected.json"
    report_path = tmp_path / Path(*relative_report.split("/"))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(expected), encoding="utf-8")

    exit_code = main(
        [
            "audit",
            "--root",
            str(tmp_path),
            "--check-report",
            relative_report,
            "--format",
            "summary",
        ]
    )

    assert exit_code == 0
    assert "source_support_measured_integration_blocked" in capsys.readouterr().out

    expected["integration"]["integration_ready"] = 0
    report_path.write_text(json.dumps(expected), encoding="utf-8")
    exit_code = main(
        [
            "audit",
            "--root",
            str(tmp_path),
            "--check-report",
            relative_report,
            "--format",
            "json",
        ]
    )

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "report_mismatch"


def test_committed_report_matches_manifest_and_aggregate_contract() -> None:
    project_root = Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (project_root / "data/manifests/ucsd-steam/source-v1.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (project_root / "data/audits/ucsd-steam/source-v1-suitability.json").read_text(
            encoding="utf-8"
        )
    )

    assert (
        report["manifest"]["sha256"] == hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()
    )
    assert report["manifest"]["source_attribution"] == manifest["source_attribution"]
    assert report["manifest"]["raw_transformations"] == []
    assert report["integration"]["integration_ready"] is False
    assert report["integration"]["blocking_reasons"] == list(BLOCKING_REASONS)
    for gate, state in EXPECTED_GATE_STATES.items():
        assert report["integration"][gate] == state

    verified_by_role = {item["role"]: item for item in report["verification"]["files"]}
    for source in manifest["files"]:
        verified = verified_by_role[source["role"]]
        assert verified["relative_path"] == source["relative_path"]
        assert verified["source_url"] == source["source_url"]
        assert verified["compressed_size_bytes"] == source["compressed_size_bytes"]
        assert verified["sha256"] == source["sha256"]

    prohibited_keys = {"user_id", "user_url", "steam_id", "review_text"}

    def collect_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {key for item in value.values() for key in collect_keys(item)}
        if isinstance(value, list):
            return {key for item in value for key in collect_keys(item)}
        return set()

    assert prohibited_keys.isdisjoint(collect_keys(report))
    privacy = report["preparation"]["privacy"]
    assert privacy == {
        "output_is_aggregate_only": True,
        "row_level_snapshot_written": False,
        "transient_profiles_exposed": False,
        "user_identifiers_emitted": False,
    }
    assert report["preparation"]["target_catalog_join"] == {
        "status": "not_attempted-no-mapping-artifact",
        "mapped_candidate_pairs": 0,
        "mapped_candidate_items": 0,
    }

    support = report["suitability"]["support_filter"]
    assert support["fixed_point_passes"] >= 1
    assert support["retained_positive_edges"] >= 2 * support["retained_users"]
    assert support["matrix_density"]["numerator"] == support["retained_positive_edges"]
    assert support["matrix_density"]["denominator"] == (
        support["retained_users"] * support["retained_items"]
    )
    assert (
        sum(support["item_support_distribution_after_filter"].values()) == support["retained_items"]
    )
    after = support["item_support_distribution_after_filter"]
    assert after["0"] == 0
    assert after["1"] == 0
    pair_support = report["suitability"]["pair_support"]
    assert pair_support["supported_pairs"] <= pair_support["distinct_pairs"]
    pair_buckets = pair_support["pair_support_distribution"]
    assert pair_support["supported_pairs"] == sum(
        pair_buckets[key] for key in ("2", "3-4", "5-9", "10+")
    )


def test_metadata_cardinality_limit_is_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source_tree(tmp_path)
    monkeypatch.setattr(ucsd_steam, "MAX_UNIQUE_ITEMS", 2)

    with pytest.raises(SourceAuditError) as raised:
        prepare_source(tmp_path)

    assert raised.value.code == "source_limit_exceeded"


def test_metadata_title_metric_accepts_either_valid_name_field(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)
    metadata = [
        {"id": "10", "title": 123, "app_name": "Valid app name"},
        {"id": "20", "title": "   ", "app_name": "Valid fallback"},
        {"id": "30", "title": None, "app_name": None},
    ]
    _rewrite_manifest_entry(tmp_path, "v2-item-metadata", _literal_lines(metadata))

    report = prepare_source(tmp_path)
    profile = report["preparation"]["source_profiles"]["v2_item_metadata"]

    assert profile["records_without_title_or_app_name"] == 1
