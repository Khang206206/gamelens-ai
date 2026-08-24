from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import itertools
import json
import math
import re
import sys
import zlib
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

MANIFEST_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
DATASET_NAME = "ucsd-steam"
SOURCE_KIND = "external_snapshot"
SOURCE_STATUS = "local-raw-sources-verified-not-integrated"
SOURCE_FORMAT = "gzip-python-literal-lines"
PREPARATION_POLICY_ID = "ucsd-steam-review-recommend-preparation-v1"

EXPECTED_ROLES = (
    "v1-user-items",
    "v1-reviews",
    "v2-item-metadata",
)
EXPECTED_PATHS = {
    "v1-user-items": (
        "data/external/ucsd-steam/payload/v1-user-items/australian_users_items.json.gz"
    ),
    "v1-reviews": ("data/external/ucsd-steam/payload/v1-reviews/australian_user_reviews.json.gz"),
    "v2-item-metadata": ("data/external/ucsd-steam/payload/v2-item-metadata/steam_games.json.gz"),
}
EXPECTED_DATASET_PAGE = "https://cseweb.ucsd.edu/~jmcauley/datasets.html"
EXPECTED_SOURCE_ATTRIBUTION = "UCSD McAuley Lab"
EXPECTED_RETRIEVED_ON = "2026-08-19"
EXPECTED_SOURCE_URLS = {
    "v1-user-items": (
        "https://mcauleylab.ucsd.edu/public_datasets/data/steam/australian_users_items.json.gz"
    ),
    "v1-reviews": (
        "https://mcauleylab.ucsd.edu/public_datasets/data/steam/australian_user_reviews.json.gz"
    ),
    "v2-item-metadata": "https://cseweb.ucsd.edu/~wckang/steam_games.json.gz",
}
EXPECTED_SOURCE_HOSTS = frozenset({"cseweb.ucsd.edu", "mcauleylab.ucsd.edu"})
EXPECTED_GATE_STATES = {
    "source_provenance": "recorded-not-approved-for-ingestion",
    "license_and_redistribution": "blocked-no-recorded-license",
    "label_authority": "blocked-preparation-signal-not-approved-label",
    "target_catalog_mapping": "blocked-no-mapping-artifact",
    "fixture_activation": "blocked-no-activation-fixture-evidence",
    "live_data_activation": "blocked-no-consent-lifecycle-evidence",
}
BLOCKING_REASONS = (
    "external_source_not_integrated",
    "fixture_activation_gate_not_evidenced",
    "license_and_redistribution_not_approved",
    "live_data_consent_and_lifecycle_not_evidenced",
    "source_provenance_not_approved_for_ingestion",
    "stage_5_label_authority_not_approved",
    "target_catalog_mapping_not_evidenced",
)

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ITEM_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
MAX_MANIFEST_BYTES = 128 * 1024
MAX_REPORT_BYTES = 2 * 1024 * 1024
MAX_SOURCE_FILES = len(EXPECTED_ROLES)
MAX_COMPRESSED_FILE_BYTES = 1_000_000_000
MAX_UNCOMPRESSED_FILE_BYTES = 2_000_000_000
MAX_LINE_BYTES = 2 * 1024 * 1024
MAX_TOP_LEVEL_RECORDS = 5_000_000
MAX_NESTED_RECORDS = 20_000_000
MAX_UNIQUE_USERS = 500_000
MAX_UNIQUE_ITEMS = 100_000
MAX_REVIEW_PAIRS = 2_000_000
MAX_PAIR_CONTRIBUTIONS = 10_000_000
MAX_DISTINCT_PAIRS = 1_000_000
MAX_USER_ID_CHARACTERS = 256
MAX_ITEM_ID_CHARACTERS = 32

MIN_PROFILE_ITEMS = 2
MIN_ITEM_SUPPORT = 2
MIN_PAIR_SUPPORT = 2
MIN_ACTIVATION_USERS = 10
MIN_ACTIVATION_EDGES = 20
MIN_ACTIVATION_ITEMS = 5


class SourceAuditError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SourceFile:
    role: str
    relative_path: str
    source_url: str
    compressed_size_bytes: int
    sha256: str
    uncompressed_size_bytes: int
    line_count: int
    max_line_bytes: int


@dataclass(frozen=True)
class SourceManifest:
    relative_path: str
    value: Mapping[str, Any]
    fingerprint: str
    files: tuple[SourceFile, ...]
    gates: Mapping[str, str]


@dataclass(frozen=True)
class ScanMetrics:
    line_count: int
    blank_line_count: int
    uncompressed_size_bytes: int
    max_line_bytes: int


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant is not allowed: {value}")


def _parse_finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Non-finite JSON number is not allowed")
    return parsed


def _load_json(path: Path, *, maximum_bytes: int, code: str) -> object:
    try:
        with path.open("rb") as stream:
            payload = stream.read(maximum_bytes + 1)
        if not 0 < len(payload) <= maximum_bytes:
            raise SourceAuditError(code, "JSON input size is outside the allowed range")
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
            parse_float=_parse_finite_json_float,
        )
        canonical_json_bytes(value)
        return value
    except SourceAuditError:
        raise
    except (
        OSError,
        RecursionError,
        UnicodeDecodeError,
        UnicodeEncodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise SourceAuditError(code, "JSON input is missing or invalid") from error


def _resolve_under(root: Path, value: str, *, code: str) -> tuple[Path, str]:
    pure = PurePosixPath(value.replace("\\", "/"))
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise SourceAuditError(code, "Path must be a safe project-relative path")
    relative = pure.as_posix()
    resolved = (root / Path(*pure.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise SourceAuditError(code, "Path escapes the project root") from error
    return resolved, relative


def _manifest_path(root: Path, value: str | Path) -> tuple[Path, str]:
    candidate = Path(value)
    if candidate.is_absolute():
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as error:
            raise SourceAuditError(
                "manifest_path_invalid", "Manifest path escapes the project root"
            ) from error
        return resolved, relative
    return _resolve_under(root, candidate.as_posix(), code="manifest_path_invalid")


def _required_string(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise SourceAuditError(
            "manifest_invalid", f"Manifest field {key} must be a non-empty string"
        )
    return item


def _required_positive_int(value: Mapping[str, Any], key: str, *, maximum: int) -> int:
    item = value.get(key)
    if type(item) is not int or not 0 < item <= maximum:
        raise SourceAuditError(
            "manifest_invalid", f"Manifest field {key} is outside the allowed range"
        )
    return item


def _validate_source_url(value: str) -> None:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError as error:
        raise SourceAuditError("manifest_invalid", "Source URL is malformed") from error
    if (
        parsed.scheme != "https"
        or hostname not in EXPECTED_SOURCE_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise SourceAuditError("manifest_invalid", "Source URL is not an approved HTTPS URL")


def _validate_retrieved_on(value: str) -> None:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise SourceAuditError(
            "manifest_invalid", "Manifest retrieval date must use YYYY-MM-DD"
        ) from error
    if parsed.isoformat() != value:
        raise SourceAuditError("manifest_invalid", "Manifest retrieval date must use YYYY-MM-DD")
    if value != EXPECTED_RETRIEVED_ON:
        raise SourceAuditError("manifest_invalid", "Manifest retrieval date is not frozen")


def load_manifest(root: str | Path, manifest_path: str | Path) -> SourceManifest:
    project_root = Path(root).resolve()
    if not project_root.is_dir():
        raise SourceAuditError("project_root_invalid", "Project root is not a directory")
    path, relative_path = _manifest_path(project_root, manifest_path)
    value = _load_json(path, maximum_bytes=MAX_MANIFEST_BYTES, code="manifest_invalid")
    if not isinstance(value, dict):
        raise SourceAuditError("manifest_invalid", "Source manifest must be an object")
    schema_version = value.get("manifest_schema_version")
    if type(schema_version) is not int or schema_version != MANIFEST_SCHEMA_VERSION:
        raise SourceAuditError("manifest_schema_incompatible", "Source manifest schema is invalid")
    if value.get("dataset") != DATASET_NAME or value.get("status") != SOURCE_STATUS:
        raise SourceAuditError("manifest_invalid", "Source manifest identity or status is invalid")
    if value.get("source_format") != SOURCE_FORMAT:
        raise SourceAuditError("manifest_invalid", "Source format is not the frozen safe format")
    if _required_string(value, "source_attribution") != EXPECTED_SOURCE_ATTRIBUTION:
        raise SourceAuditError("manifest_invalid", "Source attribution is not the frozen value")
    retrieved_on = _required_string(value, "retrieved_on")
    _validate_retrieved_on(retrieved_on)
    dataset_page = _required_string(value, "dataset_page")
    _validate_source_url(dataset_page)
    if dataset_page != EXPECTED_DATASET_PAGE:
        raise SourceAuditError("manifest_invalid", "Dataset page is not the frozen source URL")
    if value.get("raw_transformations") != []:
        raise SourceAuditError("manifest_invalid", "Raw transformations must remain empty")
    if value.get("redistribution_status") != "not-assessed-do-not-redistribute":
        raise SourceAuditError("manifest_invalid", "Redistribution must remain fail-closed")
    if value.get("citation_requested") is not True:
        raise SourceAuditError("manifest_invalid", "Citation request must be explicit")

    raw_gates = value.get("integration_gates")
    if not isinstance(raw_gates, dict) or raw_gates != EXPECTED_GATE_STATES:
        raise SourceAuditError(
            "manifest_invalid", "Integration gates are missing or not fail-closed"
        )

    raw_files = value.get("files")
    if not isinstance(raw_files, list) or len(raw_files) != MAX_SOURCE_FILES:
        raise SourceAuditError("manifest_invalid", "Source manifest file set is incomplete")
    by_role: dict[str, SourceFile] = {}
    seen_paths: set[str] = set()
    for raw_file in raw_files:
        if not isinstance(raw_file, dict):
            raise SourceAuditError("manifest_invalid", "Source file entry must be an object")
        role = _required_string(raw_file, "role")
        relative = _required_string(raw_file, "relative_path")
        source_url = _required_string(raw_file, "source_url")
        checksum = _required_string(raw_file, "sha256")
        if role not in EXPECTED_ROLES or role in by_role:
            raise SourceAuditError("manifest_invalid", "Source roles must be exact and unique")
        if relative != EXPECTED_PATHS[role] or relative in seen_paths:
            raise SourceAuditError("manifest_invalid", "Source paths must be exact and unique")
        _resolve_under(project_root, relative, code="manifest_path_invalid")
        _validate_source_url(source_url)
        if SHA256_PATTERN.fullmatch(checksum) is None:
            raise SourceAuditError("manifest_invalid", "Source SHA-256 is invalid")
        if source_url != EXPECTED_SOURCE_URLS[role]:
            raise SourceAuditError("manifest_invalid", "Source URL is not frozen for its role")
        by_role[role] = SourceFile(
            role=role,
            relative_path=relative,
            source_url=source_url,
            compressed_size_bytes=_required_positive_int(
                raw_file, "compressed_size_bytes", maximum=MAX_COMPRESSED_FILE_BYTES
            ),
            sha256=checksum,
            uncompressed_size_bytes=_required_positive_int(
                raw_file, "uncompressed_size_bytes", maximum=MAX_UNCOMPRESSED_FILE_BYTES
            ),
            line_count=_required_positive_int(
                raw_file, "line_count", maximum=MAX_TOP_LEVEL_RECORDS
            ),
            max_line_bytes=_required_positive_int(
                raw_file, "max_line_bytes", maximum=MAX_LINE_BYTES
            ),
        )
        seen_paths.add(relative)
    if set(by_role) != set(EXPECTED_ROLES):
        raise SourceAuditError("manifest_invalid", "Source role set is incomplete")
    try:
        fingerprint = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    except (UnicodeEncodeError, ValueError) as error:
        raise SourceAuditError(
            "manifest_invalid", "Source manifest contains non-canonical JSON text"
        ) from error
    return SourceManifest(
        relative_path=relative_path,
        value=value,
        fingerprint=fingerprint,
        files=tuple(by_role[role] for role in EXPECTED_ROLES),
        gates=dict(raw_gates),
    )


def _sha256_file(path: Path, source: SourceFile) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            remaining = source.compressed_size_bytes
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise SourceAuditError(
                        "source_size_mismatch", f"Source size mismatch for {source.role}"
                    )
                digest.update(chunk)
                remaining -= len(chunk)
            if stream.read(1):
                raise SourceAuditError(
                    "source_size_mismatch", f"Source size mismatch for {source.role}"
                )
    except SourceAuditError:
        raise
    except OSError as error:
        raise SourceAuditError("source_unreadable", "Source file could not be read") from error
    return digest.hexdigest()


def _reject_source_link_components(root: Path, relative_path: str) -> None:
    pure = PurePosixPath(relative_path)
    current = root
    try:
        for part in pure.parts:
            current /= part
            is_junction = getattr(current, "is_junction", lambda: False)
            if current.is_symlink() or is_junction():
                raise SourceAuditError(
                    "source_path_invalid",
                    "Source path must not contain a symlink or junction",
                )
    except OSError as error:
        raise SourceAuditError("source_unreadable", "Source path metadata is unreadable") from error


def _source_path(root: Path, source: SourceFile) -> Path:
    _reject_source_link_components(root, source.relative_path)
    path, _ = _resolve_under(root, source.relative_path, code="source_path_invalid")
    try:
        if not path.is_file():
            raise SourceAuditError("source_missing", f"Source file is missing for {source.role}")
        size = path.stat().st_size
    except OSError as error:
        raise SourceAuditError("source_unreadable", "Source file metadata is unreadable") from error
    if size != source.compressed_size_bytes:
        raise SourceAuditError("source_size_mismatch", f"Source size mismatch for {source.role}")
    if _sha256_file(path, source) != source.sha256:
        raise SourceAuditError(
            "source_checksum_mismatch", f"Source checksum mismatch for {source.role}"
        )
    return path


def _verified_paths(root: Path, manifest: SourceManifest) -> dict[str, Path]:
    # Verify every compressed member before any untrusted record is parsed.
    return {source.role: _source_path(root, source) for source in manifest.files}


def _bounded_gzip_lines(path: Path, source: SourceFile) -> Iterable[tuple[int, bytes]]:
    total = 0
    line_number = 0
    line_limit = min(MAX_LINE_BYTES, source.max_line_bytes)
    try:
        with gzip.open(path, "rb") as stream:
            while True:
                line = stream.readline(line_limit + 1)
                if not line:
                    break
                line_number += 1
                if len(line) > line_limit:
                    raise SourceAuditError(
                        "source_shape_mismatch", f"Source line is too large for {source.role}"
                    )
                total += len(line)
                if total > source.uncompressed_size_bytes:
                    raise SourceAuditError(
                        "source_shape_mismatch",
                        f"Expanded source is larger than recorded for {source.role}",
                    )
                if total > MAX_UNCOMPRESSED_FILE_BYTES:
                    raise SourceAuditError(
                        "source_limit_exceeded",
                        f"Uncompressed source is too large for {source.role}",
                    )
                if line_number > source.line_count:
                    raise SourceAuditError(
                        "source_shape_mismatch",
                        f"Source has more records than recorded for {source.role}",
                    )
                if line_number > MAX_TOP_LEVEL_RECORDS:
                    raise SourceAuditError(
                        "source_limit_exceeded", f"Source has too many records for {source.role}"
                    )
                yield line_number, line
    except SourceAuditError:
        raise
    except (EOFError, gzip.BadGzipFile, OSError, zlib.error) as error:
        raise SourceAuditError(
            "source_gzip_invalid", f"Invalid gzip source for {source.role}"
        ) from error


def _check_scan_metrics(source: SourceFile, metrics: ScanMetrics) -> None:
    if (
        metrics.line_count != source.line_count
        or metrics.uncompressed_size_bytes != source.uncompressed_size_bytes
        or metrics.max_line_bytes != source.max_line_bytes
        or metrics.blank_line_count != 0
    ):
        raise SourceAuditError(
            "source_shape_mismatch", f"Verified gzip shape mismatch for {source.role}"
        )


def _scan_metrics(path: Path, source: SourceFile) -> ScanMetrics:
    count = 0
    blanks = 0
    total = 0
    maximum = 0
    for _, line in _bounded_gzip_lines(path, source):
        count += 1
        total += len(line)
        maximum = max(maximum, len(line))
        if not line.strip():
            blanks += 1
    metrics = ScanMetrics(
        line_count=count,
        blank_line_count=blanks,
        uncompressed_size_bytes=total,
        max_line_bytes=maximum,
    )
    _check_scan_metrics(source, metrics)
    return metrics


def _parse_record(line: bytes, *, source: SourceFile, line_number: int) -> dict[str, Any]:
    try:
        value = ast.literal_eval(line.decode("utf-8"))
    except (
        MemoryError,
        RecursionError,
        SyntaxError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ) as error:
        raise SourceAuditError(
            "source_parse_invalid",
            f"Invalid safe literal for {source.role} at line {line_number}",
        ) from error
    if not isinstance(value, dict):
        raise SourceAuditError(
            "source_record_invalid",
            f"Top-level record is not an object for {source.role} at line {line_number}",
        )
    return value


def _scan_records(
    path: Path,
    source: SourceFile,
    consume: Callable[[Mapping[str, Any]], None],
) -> ScanMetrics:
    records = 0
    blanks = 0
    total = 0
    maximum = 0
    for line_number, line in _bounded_gzip_lines(path, source):
        total += len(line)
        maximum = max(maximum, len(line))
        if not line.strip():
            blanks += 1
            continue
        records += 1
        consume(_parse_record(line, source=source, line_number=line_number))
    metrics = ScanMetrics(
        line_count=records + blanks,
        blank_line_count=blanks,
        uncompressed_size_bytes=total,
        max_line_bytes=maximum,
    )
    _check_scan_metrics(source, metrics)
    return metrics


def _verification_file_report(source: SourceFile, metrics: ScanMetrics) -> dict[str, object]:
    return {
        "role": source.role,
        "relative_path": source.relative_path,
        "source_url": source.source_url,
        "compressed_size_bytes": source.compressed_size_bytes,
        "sha256": source.sha256,
        "gzip": {
            "status": "passed",
            "line_count": metrics.line_count,
            "blank_line_count": metrics.blank_line_count,
            "uncompressed_size_bytes": metrics.uncompressed_size_bytes,
            "max_line_bytes": metrics.max_line_bytes,
        },
    }


def _gate_report(manifest: SourceManifest) -> dict[str, object]:
    return {
        "integration_ready": False,
        "source_identity": "passed-local-size-sha256-gzip-shape-with-post-scan-identity-check",
        **manifest.gates,
        "blocking_reasons": list(BLOCKING_REASONS),
    }


def _report_base(manifest: SourceManifest, *, command: str) -> dict[str, object]:
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "command": command,
        "dataset": DATASET_NAME,
        "source_kind": SOURCE_KIND,
        "source_status": SOURCE_STATUS,
        "manifest": {
            "relative_path": manifest.relative_path,
            "dataset_page": manifest.value["dataset_page"],
            "source_attribution": manifest.value["source_attribution"],
            "raw_transformations": list(manifest.value["raw_transformations"]),
            "sha256": manifest.fingerprint,
            "retrieved_on": manifest.value["retrieved_on"],
        },
        "integration": _gate_report(manifest),
    }


def verify_source(
    root: str | Path,
    manifest_path: str | Path = "data/external/ucsd-steam/manifest.json",
) -> dict[str, object]:
    project_root = Path(root).resolve()
    manifest = load_manifest(project_root, manifest_path)
    paths = _verified_paths(project_root, manifest)
    files = [
        _verification_file_report(source, _scan_metrics(paths[source.role], source))
        for source in manifest.files
    ]
    report = _report_base(manifest, command="verify")
    # Bind the report to bytes that still match after decompression and scanning.
    _verified_paths(project_root, manifest)
    report.update(
        {
            "status": "verified_not_integrated",
            "verification": {"status": "passed", "files": files},
        }
    )
    return report


def _valid_item_id(value: object) -> str | None:
    if (
        not isinstance(value, str)
        or len(value) > MAX_ITEM_ID_CHARACTERS
        or ITEM_ID_PATTERN.fullmatch(value) is None
    ):
        return None
    return value


def _valid_user_id(value: object) -> str | None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_USER_ID_CHARACTERS
        or value != value.strip()
    ):
        return None
    return value


def _metadata_profile(
    path: Path, source: SourceFile
) -> tuple[dict[str, object], set[str], ScanMetrics]:
    counts: Counter[str] = Counter()
    item_ids: set[str] = set()
    ambiguous_item_ids: set[str] = set()

    def consume(record: Mapping[str, Any]) -> None:
        counts["records"] += 1
        item_id = _valid_item_id(record.get("id"))
        if item_id is None:
            counts["missing_or_invalid_item_ids"] += 1
        elif item_id in item_ids:
            counts["duplicate_item_id_records"] += 1
            ambiguous_item_ids.add(item_id)
        else:
            item_ids.add(item_id)
        if len(item_ids) > MAX_UNIQUE_ITEMS:
            raise SourceAuditError(
                "source_limit_exceeded", "Metadata item cardinality exceeds the audit limit"
            )
        has_title = any(
            isinstance(record.get(field), str) and bool(record[field].strip())
            for field in ("title", "app_name")
        )
        if not has_title:
            counts["records_without_title_or_app_name"] += 1

    metrics = _scan_records(path, source, consume)
    unambiguous_item_ids = item_ids - ambiguous_item_ids
    return (
        {
            "records": counts["records"],
            "distinct_item_ids": len(item_ids),
            "unambiguous_item_ids": len(unambiguous_item_ids),
            "missing_or_invalid_item_ids": counts["missing_or_invalid_item_ids"],
            "duplicate_item_id_records": counts["duplicate_item_id_records"],
            "ambiguous_item_ids_excluded_from_alignment": len(ambiguous_item_ids),
            "records_without_title_or_app_name": counts["records_without_title_or_app_name"],
        },
        unambiguous_item_ids,
        metrics,
    )


def _user_items_profile(
    path: Path, source: SourceFile
) -> tuple[dict[str, object], set[str], ScanMetrics]:
    counts: Counter[str] = Counter()
    users: set[str] = set()
    item_ids: set[str] = set()

    def consume(record: Mapping[str, Any]) -> None:
        counts["records"] += 1
        user_id = _valid_user_id(record.get("user_id"))
        if user_id is None:
            counts["records_without_user_id"] += 1
        elif user_id in users:
            counts["duplicate_user_records"] += 1
        else:
            users.add(user_id)
        if len(users) > MAX_UNIQUE_USERS:
            raise SourceAuditError("source_limit_exceeded", "User cardinality exceeds limits")
        raw_items = record.get("items")
        if not isinstance(raw_items, (list, tuple)):
            counts["records_without_item_list"] += 1
            return
        declared = record.get("items_count")
        if type(declared) is not int or declared != len(raw_items):
            counts["declared_item_count_mismatches"] += 1
        seen_in_record: set[str] = set()
        for raw_item in raw_items:
            counts["item_rows"] += 1
            if counts["item_rows"] > MAX_NESTED_RECORDS:
                raise SourceAuditError(
                    "source_limit_exceeded", "User-item source exceeds the nested-row limit"
                )
            if not isinstance(raw_item, dict):
                counts["invalid_item_rows"] += 1
                continue
            item_id = _valid_item_id(raw_item.get("item_id"))
            if item_id is None:
                counts["invalid_item_rows"] += 1
            else:
                if item_id in seen_in_record:
                    counts["duplicate_items_within_record"] += 1
                seen_in_record.add(item_id)
                item_ids.add(item_id)
                if len(item_ids) > MAX_UNIQUE_ITEMS:
                    raise SourceAuditError(
                        "source_limit_exceeded", "Item cardinality exceeds limits"
                    )
            playtime = raw_item.get("playtime_forever")
            if (
                type(playtime) not in {int, float}
                or (type(playtime) is float and not math.isfinite(playtime))
                or playtime < 0
            ):
                counts["invalid_playtime_rows"] += 1
            elif playtime > 0:
                counts["positive_playtime_rows_excluded_from_candidates"] += 1
            else:
                counts["zero_playtime_rows_excluded_from_candidates"] += 1

    metrics = _scan_records(path, source, consume)
    return (
        {
            "records": counts["records"],
            "distinct_users": len(users),
            "duplicate_user_records": counts["duplicate_user_records"],
            "records_without_user_id": counts["records_without_user_id"],
            "records_without_item_list": counts["records_without_item_list"],
            "declared_item_count_mismatches": counts["declared_item_count_mismatches"],
            "item_rows": counts["item_rows"],
            "distinct_item_ids": len(item_ids),
            "invalid_item_rows": counts["invalid_item_rows"],
            "duplicate_items_within_record": counts["duplicate_items_within_record"],
            "positive_playtime_rows_excluded_from_candidates": counts[
                "positive_playtime_rows_excluded_from_candidates"
            ],
            "zero_playtime_rows_excluded_from_candidates": counts[
                "zero_playtime_rows_excluded_from_candidates"
            ],
            "invalid_playtime_rows": counts["invalid_playtime_rows"],
        },
        item_ids,
        metrics,
    )


def _reviews_profile(
    path: Path, source: SourceFile
) -> tuple[dict[str, object], dict[tuple[str, str], int], set[str], ScanMetrics]:
    counts: Counter[str] = Counter()
    users: set[str] = set()
    item_ids: set[str] = set()
    pair_states: dict[tuple[str, str], int] = {}

    def consume(record: Mapping[str, Any]) -> None:
        counts["records"] += 1
        user_id = _valid_user_id(record.get("user_id"))
        if user_id is None:
            counts["records_without_user_id"] += 1
        elif user_id in users:
            counts["duplicate_user_records"] += 1
        else:
            users.add(user_id)
        if len(users) > MAX_UNIQUE_USERS:
            raise SourceAuditError("source_limit_exceeded", "User cardinality exceeds limits")
        raw_reviews = record.get("reviews")
        if not isinstance(raw_reviews, (list, tuple)):
            counts["records_without_review_list"] += 1
            return
        for raw_review in raw_reviews:
            counts["review_rows"] += 1
            if counts["review_rows"] > MAX_NESTED_RECORDS:
                raise SourceAuditError(
                    "source_limit_exceeded", "Review source exceeds the nested-row limit"
                )
            if not isinstance(raw_review, dict):
                counts["invalid_review_rows"] += 1
                continue
            item_id = _valid_item_id(raw_review.get("item_id"))
            recommend = raw_review.get("recommend")
            if item_id is None or user_id is None:
                counts["invalid_review_rows"] += 1
                continue
            item_ids.add(item_id)
            if len(item_ids) > MAX_UNIQUE_ITEMS:
                raise SourceAuditError("source_limit_exceeded", "Item cardinality exceeds limits")
            if recommend is True:
                counts["recommend_true_rows"] += 1
                state = 1
            elif recommend is False:
                counts["recommend_false_rows_excluded_from_candidates"] += 1
                state = 2
            else:
                counts["invalid_recommend_rows"] += 1
                continue
            pair = (user_id, item_id)
            if pair in pair_states:
                counts["duplicate_pair_rows"] += 1
                pair_states[pair] |= state
            else:
                if len(pair_states) >= MAX_REVIEW_PAIRS:
                    raise SourceAuditError(
                        "source_limit_exceeded", "Distinct review pairs exceed the audit limit"
                    )
                pair_states[pair] = state

    metrics = _scan_records(path, source, consume)
    conflicting_pairs = sum(state == 3 for state in pair_states.values())
    true_only_pairs = sum(state == 1 for state in pair_states.values())
    false_only_pairs = sum(state == 2 for state in pair_states.values())
    return (
        {
            "records": counts["records"],
            "distinct_users": len(users),
            "duplicate_user_records": counts["duplicate_user_records"],
            "records_without_user_id": counts["records_without_user_id"],
            "records_without_review_list": counts["records_without_review_list"],
            "review_rows": counts["review_rows"],
            "distinct_item_ids": len(item_ids),
            "invalid_review_rows": counts["invalid_review_rows"],
            "recommend_true_rows": counts["recommend_true_rows"],
            "recommend_false_rows_excluded_from_candidates": counts[
                "recommend_false_rows_excluded_from_candidates"
            ],
            "invalid_recommend_rows": counts["invalid_recommend_rows"],
            "unique_user_item_pairs": len(pair_states),
            "duplicate_pair_rows": counts["duplicate_pair_rows"],
            "conflicting_recommend_pairs_excluded": conflicting_pairs,
            "candidate_recommend_true_pairs": true_only_pairs,
            "false_only_pairs_excluded_from_candidates": false_only_pairs,
        },
        pair_states,
        item_ids,
        metrics,
    )


def _coverage(numerator: int, denominator: int) -> dict[str, object]:
    return {
        "matched": numerator,
        "total": denominator,
        "rate": round(numerator / denominator, 12) if denominator else None,
    }


def _profiles_from_pairs(
    pair_states: Mapping[tuple[str, str], int], metadata_item_ids: set[str]
) -> tuple[tuple[tuple[str, ...], ...], dict[str, int]]:
    profiles: dict[str, set[str]] = defaultdict(set)
    all_candidate_items: set[str] = set()
    mapped_candidate_items: set[str] = set()
    candidate_pairs = 0
    mapped_pairs = 0
    for (user_id, item_id), state in pair_states.items():
        if state != 1:
            continue
        candidate_pairs += 1
        all_candidate_items.add(item_id)
        if item_id in metadata_item_ids:
            profiles[user_id].add(item_id)
            mapped_candidate_items.add(item_id)
            mapped_pairs += 1
    canonical = tuple(sorted(tuple(sorted(items)) for items in profiles.values() if items))
    return canonical, {
        "candidate_pairs": candidate_pairs,
        "mapped_candidate_pairs": mapped_pairs,
        "candidate_distinct_items": len(all_candidate_items),
        "mapped_candidate_distinct_items": len(mapped_candidate_items),
    }


def _parse_all_sources(
    root: Path, manifest: SourceManifest
) -> tuple[dict[str, object], tuple[tuple[str, ...], ...]]:
    sources = {source.role: source for source in manifest.files}
    paths = _verified_paths(root, manifest)
    metadata, metadata_ids, metadata_metrics = _metadata_profile(
        paths["v2-item-metadata"], sources["v2-item-metadata"]
    )
    user_items, user_item_ids, user_items_metrics = _user_items_profile(
        paths["v1-user-items"], sources["v1-user-items"]
    )
    reviews, pair_states, review_item_ids, reviews_metrics = _reviews_profile(
        paths["v1-reviews"], sources["v1-reviews"]
    )
    profiles, candidate_counts = _profiles_from_pairs(pair_states, metadata_ids)
    # Detect same-shape replacement after the initial checksum gate and parsing.
    _verified_paths(root, manifest)
    metrics_by_role = {
        "v1-user-items": user_items_metrics,
        "v1-reviews": reviews_metrics,
        "v2-item-metadata": metadata_metrics,
    }
    verification_files = [
        _verification_file_report(source, metrics_by_role[source.role]) for source in manifest.files
    ]
    user_item_matches = len(user_item_ids & metadata_ids)
    review_matches = len(review_item_ids & metadata_ids)
    preparation = {
        "policy": {
            "id": PREPARATION_POLICY_ID,
            "candidate_signal": "v1 review recommend is exactly true",
            "not_an_approved_stage_5_label": True,
            "duplicate_same_flag": "collapse-user-item-pair",
            "duplicate_conflict": "exclude-user-item-pair",
            "ownership_and_playtime": "profile-only-never-a-candidate-positive",
            "target_identity": "source Steam item ID only; no GameLens mapping",
        },
        "source_profiles": {
            "v1_user_items": user_items,
            "v1_reviews": reviews,
            "v2_item_metadata": metadata,
        },
        "source_metadata_alignment": {
            "not_a_gamelens_catalog_mapping": True,
            "user_item_distinct_ids": _coverage(user_item_matches, len(user_item_ids)),
            "review_distinct_ids": _coverage(review_matches, len(review_item_ids)),
            "candidate_positive_pairs": _coverage(
                candidate_counts["mapped_candidate_pairs"], candidate_counts["candidate_pairs"]
            ),
            "candidate_positive_distinct_ids": _coverage(
                candidate_counts["mapped_candidate_distinct_items"],
                candidate_counts["candidate_distinct_items"],
            ),
        },
        "target_catalog_join": {
            "status": "not_attempted-no-mapping-artifact",
            "mapped_candidate_pairs": 0,
            "mapped_candidate_items": 0,
        },
        "privacy": {
            "output_is_aggregate_only": True,
            "user_identifiers_emitted": False,
            "row_level_snapshot_written": False,
            "transient_profiles_exposed": False,
        },
    }
    return (
        {
            "verification": {"status": "passed", "files": verification_files},
            "preparation": preparation,
        },
        profiles,
    )


def _prepare_source_with_profiles(
    root: str | Path,
    manifest_path: str | Path = "data/external/ucsd-steam/manifest.json",
) -> tuple[dict[str, object], tuple[tuple[str, ...], ...]]:
    project_root = Path(root).resolve()
    manifest = load_manifest(project_root, manifest_path)
    parsed, profiles = _parse_all_sources(project_root, manifest)
    report = _report_base(manifest, command="prepare")
    report.update({"status": "prepared_for_review_not_integrated", **parsed})
    return report, profiles


def prepare_source(
    root: str | Path,
    manifest_path: str | Path = "data/external/ucsd-steam/manifest.json",
) -> dict[str, object]:
    report, _ = _prepare_source_with_profiles(root, manifest_path)
    return report


def _bucket_counts(values: Iterable[int]) -> dict[str, int]:
    buckets = {"0": 0, "1": 0, "2": 0, "3-4": 0, "5-9": 0, "10+": 0}
    for value in values:
        if value == 0:
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


def _candidate_profile_fingerprint(profiles: Sequence[tuple[str, ...]]) -> str:
    payload = {
        "policy": PREPARATION_POLICY_ID,
        "profiles": [list(profile) for profile in sorted(profiles)],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _source_suitability(profiles: Sequence[tuple[str, ...]]) -> dict[str, object]:
    source_profile_sizes = [len(profile) for profile in profiles]
    multi_profiles = [profile for profile in profiles if len(profile) >= MIN_PROFILE_ITEMS]
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
        item for item, support in active_item_support.items() if support < MIN_ITEM_SUPPORT
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
        next_pending_items: set[str] = set()
        for profile_index in sorted(affected_profiles):
            if (
                active_profiles[profile_index]
                and len(profile_items[profile_index]) < MIN_PROFILE_ITEMS
            ):
                active_profiles[profile_index] = False
                for item in sorted(profile_items[profile_index]):
                    active_item_support[item] -= 1
                    if active_item_support[item] == 0:
                        active_items.discard(item)
                        next_pending_items.discard(item)
                    elif active_item_support[item] < MIN_ITEM_SUPPORT:
                        next_pending_items.add(item)
                profile_items[profile_index].clear()
        pending_items = next_pending_items
    retained_profiles = [
        tuple(item for item in profile if item in active_items)
        for profile_index, profile in enumerate(multi_profiles)
        if active_profiles[profile_index]
    ]
    fixed_point_passes = pruning_rounds + 1
    final_item_support = Counter(item for profile in retained_profiles for item in profile)
    retained_items = set(final_item_support)
    retained_edges = sum(map(len, retained_profiles))
    pair_contributions = sum(
        len(profile) * (len(profile) - 1) // 2 for profile in retained_profiles
    )
    if pair_contributions > MAX_PAIR_CONTRIBUTIONS:
        raise SourceAuditError(
            "source_limit_exceeded", "Candidate pair contributions exceed the audit limit"
        )
    pair_support: Counter[tuple[str, str]] = Counter()
    for profile in retained_profiles:
        for pair in itertools.combinations(profile, 2):
            if pair not in pair_support and len(pair_support) >= MAX_DISTINCT_PAIRS:
                raise SourceAuditError(
                    "source_limit_exceeded",
                    "Distinct candidate pairs exceed the audit limit",
                )
            pair_support[pair] += 1
    supported_pairs = sum(support >= MIN_PAIR_SUPPORT for support in pair_support.values())
    denominator = len(retained_profiles) * len(retained_items)

    reasons: list[str] = []
    if not profiles:
        reasons.append("no_candidate_positive_users")
    if not multi_profiles:
        reasons.append("no_multi_positive_users")
    if not retained_items:
        reasons.append("no_supported_items")
    if not supported_pairs:
        reasons.append("no_supported_pairs")
    if len(retained_profiles) < MIN_ACTIVATION_USERS:
        reasons.append("insufficient_activation_users")
    if retained_edges < MIN_ACTIVATION_EDGES:
        reasons.append("insufficient_activation_edges")
    if len(retained_items) < MIN_ACTIVATION_ITEMS:
        reasons.append("insufficient_activation_items")
    source_support_passes = not reasons

    return {
        "assessment_scope": "source-level structural support after v2 metadata alignment",
        "approved_training_eligibility": False,
        "ready_for_functional_build": False,
        "source_level_support_passes": source_support_passes,
        "source_level_reasons": reasons,
        "candidate_profile_fingerprint": _candidate_profile_fingerprint(profiles),
        "filter_order": [
            "deduplicate recommend=true by source user/item and exclude conflicts",
            "align to one unambiguous v2 metadata item",
            "retain profiles with at least two distinct items",
            "iterate support>=2 items and length>=2 profiles to a deterministic fixed point",
            "measure item pairs with support from at least two retained profiles",
        ],
        "thresholds": {
            "minimum_profile_items": MIN_PROFILE_ITEMS,
            "minimum_item_support": MIN_ITEM_SUPPORT,
            "minimum_pair_support": MIN_PAIR_SUPPORT,
            "activation_minimum_users": MIN_ACTIVATION_USERS,
            "activation_minimum_edges": MIN_ACTIVATION_EDGES,
            "activation_minimum_items": MIN_ACTIVATION_ITEMS,
        },
        "limits": {
            "maximum_line_bytes": MAX_LINE_BYTES,
            "maximum_uncompressed_file_bytes": MAX_UNCOMPRESSED_FILE_BYTES,
            "maximum_top_level_records": MAX_TOP_LEVEL_RECORDS,
            "maximum_nested_records": MAX_NESTED_RECORDS,
            "maximum_unique_users": MAX_UNIQUE_USERS,
            "maximum_unique_items": MAX_UNIQUE_ITEMS,
            "maximum_review_pairs": MAX_REVIEW_PAIRS,
            "maximum_pair_contributions": MAX_PAIR_CONTRIBUTIONS,
            "maximum_distinct_pairs": MAX_DISTINCT_PAIRS,
            "maximum_user_id_characters": MAX_USER_ID_CHARACTERS,
            "maximum_item_id_characters": MAX_ITEM_ID_CHARACTERS,
        },
        "candidate_profiles": {
            "users_with_candidate_positive": len(profiles),
            "candidate_positive_edges": sum(source_profile_sizes),
            "distinct_candidate_items": len({item for profile in profiles for item in profile}),
            "profile_size_distribution": _bucket_counts(source_profile_sizes),
        },
        "support_filter": {
            "algorithm": "deterministic-queue-bipartite-two-core-v1",
            "multi_positive_users_before_item_support": len(multi_profiles),
            "positive_edges_before_item_support": sum(map(len, multi_profiles)),
            "distinct_items_before_item_support": len(initial_item_support),
            "fixed_point_passes": fixed_point_passes,
            "retained_items": len(retained_items),
            "retained_users": len(retained_profiles),
            "retained_positive_edges": retained_edges,
            "matrix_density": {
                "numerator": retained_edges,
                "denominator": denominator,
                "rate": round(retained_edges / denominator, 12) if denominator else None,
            },
            "item_support_distribution_before_filter": _bucket_counts(
                initial_item_support.values()
            ),
            "item_support_distribution_after_filter": _bucket_counts(final_item_support.values()),
        },
        "pair_support": {
            "pair_contributions": pair_contributions,
            "distinct_pairs": len(pair_support),
            "supported_pairs": supported_pairs,
            "pair_support_distribution": _bucket_counts(pair_support.values()),
        },
        "interpretation": (
            "Passing source-level support is only evidence that the preparation policy can "
            "form a non-degenerate sparse cohort. It is not license approval, GameLens catalog "
            "coverage, integration approval, or recommendation-quality evidence."
        ),
    }


def audit_source(
    root: str | Path,
    manifest_path: str | Path = "data/external/ucsd-steam/manifest.json",
) -> dict[str, object]:
    report, candidate_profiles = _prepare_source_with_profiles(root, manifest_path)
    report["command"] = "audit"
    report["status"] = "source_support_measured_integration_blocked"
    report["suitability"] = _source_suitability(candidate_profiles)
    return report


def human_summary(report: Mapping[str, Any]) -> str:
    command = report.get("command", "audit")
    lines = [
        f"UCSD Steam {command}: {report.get('status', 'unknown')}",
        "Integration ready: no",
    ]
    error_details = report.get("error")
    if isinstance(error_details, dict):
        code = error_details.get("code", "unknown_error")
        message = error_details.get("message", "Source audit failed")
        lines.append(f"Error: {code}: {message}")
        return "\n".join(lines)

    verification = report.get("verification")
    if isinstance(verification, dict):
        files = verification.get("files")
        if isinstance(files, list):
            lines.append(f"Verified source files: {len(files)}")
    preparation = report.get("preparation")
    if isinstance(preparation, dict):
        profiles = preparation.get("source_profiles")
        if isinstance(profiles, dict):
            reviews = profiles.get("v1_reviews")
            if isinstance(reviews, dict):
                lines.append(
                    "Review rows / candidate pairs: "
                    f"{reviews.get('review_rows', 0)} / "
                    f"{reviews.get('candidate_recommend_true_pairs', 0)}"
                )
    suitability = report.get("suitability")
    if isinstance(suitability, dict):
        support = suitability.get("support_filter")
        if isinstance(support, dict):
            lines.append(
                "Source-only retained users / items / edges: "
                f"{support.get('retained_users', 0)} / "
                f"{support.get('retained_items', 0)} / "
                f"{support.get('retained_positive_edges', 0)}"
            )
        lines.append(
            "Source-level structural support: "
            + ("passes" if suitability.get("source_level_support_passes") else "does not pass")
        )
    integration = report.get("integration")
    if isinstance(integration, dict):
        reasons = integration.get("blocking_reasons")
        if isinstance(reasons, list):
            lines.append("Blocking reasons: " + ", ".join(str(reason) for reason in reasons))
    return "\n".join(lines)


def _error_report(command: str, error: SourceAuditError) -> dict[str, object]:
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "command": command,
        "dataset": DATASET_NAME,
        "status": "error",
        "error": {"code": error.code, "message": str(error)},
        "integration_ready": False,
    }


def _check_committed_report(
    root: str | Path, report_path: str | Path, actual: Mapping[str, Any]
) -> None:
    project_root = Path(root).resolve()
    path, _ = _resolve_under(
        project_root,
        Path(report_path).as_posix(),
        code="report_path_invalid",
    )
    expected = _load_json(path, maximum_bytes=MAX_REPORT_BYTES, code="report_invalid")
    try:
        expected_bytes = canonical_json_bytes(expected)
        actual_bytes = canonical_json_bytes(actual)
    except (UnicodeEncodeError, ValueError) as error:
        raise SourceAuditError("report_invalid", "Audit report is not canonical JSON") from error
    if expected_bytes != actual_bytes:
        raise SourceAuditError("report_mismatch", "Committed audit report does not match")


def _print_report(report: Mapping[str, Any], output_format: str) -> None:
    if output_format == "summary":
        print(human_summary(report))
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only UCSD Steam source verification and aggregate ingestion-preparation audit"
        )
    )
    parser.add_argument("command", choices=("verify", "prepare", "audit"))
    parser.add_argument("--root", default=".", help="Repository root (read-only)")
    parser.add_argument(
        "--manifest",
        default="data/external/ucsd-steam/manifest.json",
        help="Manifest path under the repository root",
    )
    parser.add_argument(
        "--check-report",
        help="For audit only, compare against this project-relative JSON report",
    )
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    args = parser.parse_args(argv)
    command = str(args.command)
    try:
        if args.check_report is not None and command != "audit":
            raise SourceAuditError(
                "report_check_invalid", "--check-report is valid only with audit"
            )
        if command == "verify":
            report = verify_source(args.root, args.manifest)
        elif command == "prepare":
            report = prepare_source(args.root, args.manifest)
        else:
            report = audit_source(args.root, args.manifest)
            if args.check_report is not None:
                _check_committed_report(
                    args.root,
                    str(args.check_report),
                    report,
                )
    except SourceAuditError as error:
        _print_report(_error_report(command, error), args.format)
        return 2
    _print_report(report, args.format)
    return 0


if __name__ == "__main__":
    sys.exit(main())
