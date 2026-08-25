import hashlib
import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

import gamelens_recommender.collaborative_artifacts as artifact_module
from gamelens_recommender.collaborative_artifacts import (
    CollaborativeArtifactError,
    CollaborativeBuildMetadata,
    build_collaborative_artifact,
    inspect_collaborative_artifact,
    load_collaborative_artifact,
)
from gamelens_recommender.collaborative_training import (
    CollaborativeNeighborhoods,
    quantize_similarity,
)

EXPECTED_FILES = {
    "manifest.json",
    "item-slugs.json",
    "item-support.npy",
    "neighbors-indices.npy",
    "neighbors-indptr.npy",
    "similarity-units.npy",
    "pair-support.npy",
}
BUILT_AT = datetime(2026, 8, 25, 1, 2, 3, 456789, tzinfo=UTC)
VALID_UNTIL = datetime(2099, 1, 1, tzinfo=UTC)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _npy_bytes(value: np.ndarray, *, allow_pickle: bool = False) -> bytes:
    stream = BytesIO()
    np.save(stream, value, allow_pickle=allow_pickle)
    return stream.getvalue()


def _fixture_metadata() -> CollaborativeBuildMetadata:
    return CollaborativeBuildMetadata(
        source_kind="fixture",
        catalog_fingerprint="a" * 64,
        interaction_fingerprint="b" * 64,
        build_id="stage5-artifact-fixture-v1",
        built_at=BUILT_AT,
        fixture_id="stage-5-artifact-tests-v1",
        valid_until=VALID_UNTIL,
    )


def _live_metadata() -> CollaborativeBuildMetadata:
    return CollaborativeBuildMetadata(
        source_kind="live",
        catalog_fingerprint="a" * 64,
        interaction_fingerprint="b" * 64,
        build_id="stage5-live-build-v1",
        built_at=BUILT_AT,
        cutoff=BUILT_AT - timedelta(minutes=5),
        consent_version="stage-5-contribution-v1",
        data_revision=7,
        valid_until=VALID_UNTIL,
    )


def _neighborhoods() -> CollaborativeNeighborhoods:
    item_slugs = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot")
    item_support = np.asarray([6, 7, 7, 2, 7, 7], dtype=np.int64)
    neighbor_indptr = np.asarray([0, 2, 4, 7, 8, 10, 12], dtype=np.int32)
    neighbor_indices = np.asarray(
        [1, 2, 0, 2, 0, 1, 4, 5, 2, 5, 3, 4],
        dtype=np.int32,
    )
    pair_support = np.asarray(
        [2, 2, 2, 3, 2, 3, 2, 2, 2, 2, 2, 2],
        dtype=np.int64,
    )
    similarities: list[int] = []
    for source, (start, end) in enumerate(
        zip(neighbor_indptr[:-1], neighbor_indptr[1:], strict=True)
    ):
        for offset in range(int(start), int(end)):
            target = int(neighbor_indices[offset])
            raw = np.float64(pair_support[offset]) / np.sqrt(
                np.float64(item_support[source]) * np.float64(item_support[target])
            )
            similarities.append(quantize_similarity(raw))
    return CollaborativeNeighborhoods(
        item_slugs=item_slugs,
        item_support=item_support,
        neighbor_indices=neighbor_indices,
        neighbor_indptr=neighbor_indptr,
        similarity_units=np.asarray(similarities, dtype=np.int32),
        pair_support=pair_support,
        retained_contributors=12,
        retained_positive_edges=36,
        pair_contributions=36,
    )


def _build_fixture(path: Path) -> Path:
    return build_collaborative_artifact(
        _neighborhoods(),
        path,
        metadata=_fixture_metadata(),
        allow_fixture=True,
    )


def _rewrite_member(root: Path, name: str, payload: bytes) -> None:
    (root / name).write_bytes(payload)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["members"][name] = {
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    manifest_path.write_bytes(_canonical_json(manifest))


def _rewrite_array(root: Path, name: str, value: np.ndarray) -> None:
    _rewrite_member(root, name, _npy_bytes(value))


def _artifact_bytes(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.iterdir()}


def test_fixture_round_trip_is_deterministic_private_and_deeply_immutable(
    tmp_path: Path,
) -> None:
    first = _build_fixture(tmp_path / "first")
    second = _build_fixture(tmp_path / "second")

    assert {path.name for path in first.iterdir()} == EXPECTED_FILES
    assert _artifact_bytes(first) == _artifact_bytes(second)
    with pytest.raises(CollaborativeArtifactError) as denied:
        load_collaborative_artifact(first, now=BUILT_AT)
    assert denied.value.code == "fixture_not_allowed"

    before = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_size)
        for path in first.iterdir()
    }
    loaded = load_collaborative_artifact(
        first,
        allow_fixture=True,
        expected_catalog_fingerprint="a" * 64,
        now=BUILT_AT,
    )
    report = inspect_collaborative_artifact(first, allow_fixture=True, now=BUILT_AT)
    after = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_size)
        for path in first.iterdir()
    }

    assert before == after
    assert loaded.item_slugs == _neighborhoods().item_slugs
    assert loaded.slug_to_index == {slug: index for index, slug in enumerate(loaded.item_slugs)}
    assert all(
        array.flags.writeable is False
        for array in (
            loaded.item_support,
            loaded.neighbor_indices,
            loaded.neighbor_indptr,
            loaded.similarity_units,
            loaded.pair_support,
        )
    )
    with pytest.raises(ValueError):
        loaded.item_support[0] = 1
    with pytest.raises(ValueError):
        loaded.item_support.setflags(write=True)
    with pytest.raises(TypeError):
        loaded.slug_to_index["golf"] = 6
    with pytest.raises(TypeError):
        loaded.manifest["matrix"]["retained_items"] = 7

    assert report["status"] == "valid"
    assert report["source"]["kind"] == "fixture"
    assert report["matrix"]["retained_contributors"] == 12
    report_bytes = _canonical_json(report)
    assert all(slug.encode() not in report_bytes for slug in loaded.item_slugs)
    artifact_payload = b"".join(_artifact_bytes(first).values())
    assert not any(
        marker in artifact_payload
        for marker in (
            b"synthetic-profile-01",
            b"profile_key",
            b"user_id",
            b"anonymous_token_digest",
            b"credential",
        )
    )


@pytest.mark.parametrize("kind", ["missing", "extra-file", "extra-directory"])
def test_loader_rejects_missing_and_extra_directory_members(
    tmp_path: Path,
    kind: str,
) -> None:
    root = _build_fixture(tmp_path / kind)
    if kind == "missing":
        (root / "pair-support.npy").unlink()
        expected_code = "artifact_missing"
    elif kind == "extra-file":
        (root / "unexpected.bin").write_bytes(b"unexpected")
        expected_code = "artifact_path_invalid"
    else:
        (root / "nested").mkdir()
        expected_code = "artifact_path_invalid"

    with pytest.raises(CollaborativeArtifactError) as caught:
        load_collaborative_artifact(root, allow_fixture=True, now=BUILT_AT)
    assert caught.value.code == expected_code


def test_loader_rejects_member_and_root_symlinks(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path / "artifact")
    member = root / "pair-support.npy"
    outside = tmp_path / "outside.npy"
    member.replace(outside)
    try:
        member.symlink_to(outside)
    except OSError:
        pytest.skip("Symbolic links are unavailable in this Windows environment")
    with pytest.raises(CollaborativeArtifactError) as member_error:
        load_collaborative_artifact(root, allow_fixture=True, now=BUILT_AT)
    assert member_error.value.code == "artifact_path_invalid"

    link = tmp_path / "artifact-link"
    try:
        link.symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symbolic links are unavailable in this Windows environment")
    with pytest.raises(CollaborativeArtifactError) as root_error:
        load_collaborative_artifact(link, allow_fixture=True, now=BUILT_AT)
    assert root_error.value.code == "artifact_path_invalid"


@pytest.mark.parametrize("corruption", ["duplicate-key", "non-finite", "non-canonical"])
def test_loader_rejects_non_strict_manifest_json(tmp_path: Path, corruption: str) -> None:
    root = _build_fixture(tmp_path / corruption)
    manifest_path = root / "manifest.json"
    payload = manifest_path.read_bytes()
    if corruption == "duplicate-key":
        payload = b'{"artifact_schema_version":1,' + payload[1:]
    elif corruption == "non-finite":
        payload = payload.replace(b'"artifact_schema_version":1', b'"artifact_schema_version":NaN')
    else:
        payload += b"\n"
    manifest_path.write_bytes(payload)

    with pytest.raises(CollaborativeArtifactError) as caught:
        load_collaborative_artifact(root, allow_fixture=True, now=BUILT_AT)
    assert caught.value.code == "manifest_invalid"


def test_loader_rejects_manifest_traversal_and_checksum_corruption(tmp_path: Path) -> None:
    traversal_root = _build_fixture(tmp_path / "traversal")
    manifest_path = traversal_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["members"]["../pair-support.npy"] = manifest["members"].pop("pair-support.npy")
    manifest_path.write_bytes(_canonical_json(manifest))
    with pytest.raises(CollaborativeArtifactError) as traversal:
        load_collaborative_artifact(traversal_root, allow_fixture=True, now=BUILT_AT)
    assert traversal.value.code == "manifest_invalid"

    checksum_root = _build_fixture(tmp_path / "checksum")
    payload_path = checksum_root / "pair-support.npy"
    payload = bytearray(payload_path.read_bytes())
    payload[-1] ^= 1
    payload_path.write_bytes(payload)
    with pytest.raises(CollaborativeArtifactError) as checksum:
        load_collaborative_artifact(checksum_root, allow_fixture=True, now=BUILT_AT)
    assert checksum.value.code == "artifact_integrity_failed"


@pytest.mark.parametrize(
    ("corruption", "expected_code"),
    [
        ("object-dtype", "artifact_dtype_invalid"),
        ("wrong-dtype", "artifact_dtype_invalid"),
        ("wrong-shape", "artifact_shape_invalid"),
        ("trailing-payload", "artifact_numeric_invalid"),
    ],
)
def test_loader_rejects_unsafe_or_malformed_npy_members(
    tmp_path: Path,
    corruption: str,
    expected_code: str,
) -> None:
    root = _build_fixture(tmp_path / corruption)
    values = _neighborhoods().neighbor_indices
    if corruption == "object-dtype":
        payload = _npy_bytes(np.asarray(["x"] * len(values), dtype=object), allow_pickle=True)
    elif corruption == "wrong-dtype":
        payload = _npy_bytes(values.astype(np.int64))
    elif corruption == "wrong-shape":
        payload = _npy_bytes(values[:-1])
    else:
        payload = _npy_bytes(values) + b"trailing"
    _rewrite_member(root, "neighbors-indices.npy", payload)

    with pytest.raises(CollaborativeArtifactError) as caught:
        load_collaborative_artifact(root, allow_fixture=True, now=BUILT_AT)
    assert caught.value.code == expected_code


@pytest.mark.parametrize(
    ("corruption", "member", "expected_code"),
    [
        ("indptr-start", "neighbors-indptr.npy", "artifact_format_invalid"),
        ("unsorted", "neighbors-indices.npy", "artifact_format_invalid"),
        ("duplicate", "neighbors-indices.npy", "artifact_format_invalid"),
        ("self-edge", "neighbors-indices.npy", "artifact_format_invalid"),
        ("similarity", "similarity-units.npy", "artifact_numeric_invalid"),
        ("pair-support", "pair-support.npy", "artifact_numeric_invalid"),
        ("item-support", "item-support.npy", "artifact_numeric_invalid"),
    ],
)
def test_loader_rejects_checksum_valid_semantic_corruption(
    tmp_path: Path,
    corruption: str,
    member: str,
    expected_code: str,
) -> None:
    root = _build_fixture(tmp_path / corruption)
    neighborhoods = _neighborhoods()
    values_by_member = {
        "neighbors-indptr.npy": neighborhoods.neighbor_indptr,
        "neighbors-indices.npy": neighborhoods.neighbor_indices,
        "similarity-units.npy": neighborhoods.similarity_units,
        "pair-support.npy": neighborhoods.pair_support,
        "item-support.npy": neighborhoods.item_support,
    }
    values = values_by_member[member].copy()
    if corruption == "indptr-start":
        values[0] = 1
    elif corruption == "unsorted":
        values[0], values[1] = values[1], values[0]
    elif corruption == "duplicate":
        values[1] = values[0]
    elif corruption == "self-edge":
        values[0] = 0
    elif corruption == "similarity":
        values[0] += 1
    elif corruption == "pair-support":
        values[0] = 1
    else:
        values[0] += 1
    _rewrite_array(root, member, values)

    with pytest.raises(CollaborativeArtifactError) as caught:
        load_collaborative_artifact(root, allow_fixture=True, now=BUILT_AT)
    assert caught.value.code == expected_code


def test_loader_rejects_noncanonical_item_axis(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path / "slugs")
    slugs = list(reversed(_neighborhoods().item_slugs))
    _rewrite_member(root, "item-slugs.json", _canonical_json(slugs))

    with pytest.raises(CollaborativeArtifactError) as caught:
        load_collaborative_artifact(root, allow_fixture=True, now=BUILT_AT)
    assert caught.value.code == "artifact_format_invalid"


def test_loader_rejects_impossible_pair_contribution_aggregate(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path / "impossible-pair-contributions")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["matrix"]["pair_contributions"] = 181
    manifest_path.write_bytes(_canonical_json(manifest))

    with pytest.raises(CollaborativeArtifactError) as caught:
        load_collaborative_artifact(root, allow_fixture=True, now=BUILT_AT)
    assert caught.value.code == "artifact_numeric_invalid"


def test_loader_rejects_inconsistent_mutual_neighbors(tmp_path: Path) -> None:
    root = _build_fixture(tmp_path / "inconsistent-mutual-neighbors")
    neighborhoods = _neighborhoods()
    pair_support = neighborhoods.pair_support.copy()
    similarity_units = neighborhoods.similarity_units.copy()

    reverse_offset = 2  # bravo -> alpha; alpha -> bravo is offset zero.
    pair_support[reverse_offset] = 3
    similarity_units[reverse_offset] = quantize_similarity(
        np.float64(pair_support[reverse_offset])
        / np.sqrt(np.float64(neighborhoods.item_support[0] * neighborhoods.item_support[1]))
    )
    _rewrite_array(root, "pair-support.npy", pair_support)
    _rewrite_array(root, "similarity-units.npy", similarity_units)

    with pytest.raises(CollaborativeArtifactError) as caught:
        load_collaborative_artifact(root, allow_fixture=True, now=BUILT_AT)
    assert caught.value.code == "artifact_numeric_invalid"


def test_live_lifecycle_expectations_and_expiry_are_fail_closed(tmp_path: Path) -> None:
    revisions: list[int] = []

    def verify_revision(revision: int) -> bool:
        revisions.append(revision)
        return True

    root = build_collaborative_artifact(
        _neighborhoods(),
        tmp_path / "live",
        metadata=_live_metadata(),
        revision_check=verify_revision,
    )
    assert revisions == [7]
    load_collaborative_artifact(
        root,
        expected_catalog_fingerprint="a" * 64,
        expected_data_revision=7,
        expected_consent_version="stage-5-contribution-v1",
        now=BUILT_AT,
    )

    checks = (
        ({"expected_catalog_fingerprint": "c" * 64}, "catalog_mismatch"),
        ({"expected_data_revision": 8}, "artifact_stale_revision"),
        (
            {"expected_consent_version": "stage-5-contribution-v2"},
            "consent_policy_incompatible",
        ),
        ({"now": VALID_UNTIL}, "artifact_expired"),
    )
    for keywords, expected_code in checks:
        with pytest.raises(CollaborativeArtifactError) as caught:
            load_collaborative_artifact(root, **keywords)
        assert caught.value.code == expected_code

    fixture = _build_fixture(tmp_path / "expiring-fixture")
    with pytest.raises(CollaborativeArtifactError) as expired_fixture:
        load_collaborative_artifact(
            fixture,
            allow_fixture=True,
            now=VALID_UNTIL,
        )
    assert expired_fixture.value.code == "artifact_expired"


def test_live_build_requires_successful_last_moment_revision_check(tmp_path: Path) -> None:
    without_check = tmp_path / "without-check"
    with pytest.raises(CollaborativeArtifactError) as missing:
        build_collaborative_artifact(
            _neighborhoods(),
            without_check,
            metadata=_live_metadata(),
        )
    assert missing.value.code == "revision_race"
    assert not without_check.exists()

    changed = tmp_path / "changed"
    with pytest.raises(CollaborativeArtifactError) as stale:
        build_collaborative_artifact(
            _neighborhoods(),
            changed,
            metadata=_live_metadata(),
            revision_check=lambda _: False,
        )
    assert stale.value.code == "revision_race"
    assert not changed.exists()
    assert not tuple(tmp_path.glob(".changed.tmp-*"))


def test_build_does_not_promote_an_already_expired_bundle(tmp_path: Path) -> None:
    target = tmp_path / "expired"
    built_at = datetime(2000, 1, 1, tzinfo=UTC)
    metadata = CollaborativeBuildMetadata(
        source_kind="fixture",
        catalog_fingerprint="a" * 64,
        interaction_fingerprint="b" * 64,
        build_id="expired-fixture-v1",
        built_at=built_at,
        fixture_id="stage-5-expired-fixture-v1",
        valid_until=built_at + timedelta(days=1),
    )

    with pytest.raises(CollaborativeArtifactError) as caught:
        build_collaborative_artifact(
            _neighborhoods(),
            target,
            metadata=metadata,
            allow_fixture=True,
        )
    assert caught.value.code == "artifact_expired"
    assert not target.exists()
    assert not tuple(tmp_path.glob(".expired.tmp-*"))


def test_promotion_never_overwrites_target_or_promotes_after_revision_race(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "owner.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(CollaborativeArtifactError) as occupied:
        _build_fixture(existing)
    assert occupied.value.code == "artifact_target_exists"
    assert marker.read_text(encoding="utf-8") == "keep"

    raced = tmp_path / "raced"

    def create_competing_target(_: int) -> bool:
        raced.mkdir()
        (raced / "owner.txt").write_text("keep", encoding="utf-8")
        return True

    with pytest.raises(CollaborativeArtifactError) as race:
        build_collaborative_artifact(
            _neighborhoods(),
            raced,
            metadata=_live_metadata(),
            revision_check=create_competing_target,
        )
    assert race.value.code == "artifact_target_exists"
    assert (raced / "owner.txt").read_text(encoding="utf-8") == "keep"
    assert not tuple(tmp_path.glob(".raced.tmp-*"))


def test_atomic_promotion_does_not_replace_target_created_after_precheck(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "late-race"
    original = artifact_module._rename_directory_no_replace
    competing_inode: list[int] = []

    def create_target_then_promote(source: Path, destination: Path) -> None:
        destination.mkdir()
        competing_inode.append(destination.stat().st_ino)
        original(source, destination)

    monkeypatch.setattr(
        artifact_module,
        "_rename_directory_no_replace",
        create_target_then_promote,
    )
    with pytest.raises(CollaborativeArtifactError) as caught:
        _build_fixture(target)

    assert caught.value.code == "artifact_target_exists"
    assert target.stat().st_ino == competing_inode[0]
    assert not tuple(target.iterdir())
    assert not tuple(tmp_path.glob(".late-race.tmp-*"))


def test_production_loader_failure_cleans_temporary_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "invalid"

    def reject_temporary(*args: object, **kwargs: object) -> None:
        raise CollaborativeArtifactError("artifact_integrity_failed", "injected")

    monkeypatch.setattr(artifact_module, "load_collaborative_artifact", reject_temporary)
    with pytest.raises(CollaborativeArtifactError) as caught:
        _build_fixture(target)
    assert caught.value.code == "artifact_integrity_failed"
    assert not target.exists()
    assert not tuple(tmp_path.glob(".invalid.tmp-*"))
    assert not (tmp_path / ".invalid.promotion.lock").exists()
