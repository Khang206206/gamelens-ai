import subprocess
import sys


def _run_help(module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *arguments, "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_collaborative_artifact_module_starts_in_a_fresh_interpreter() -> None:
    result = _run_help("app.commands.collaborative_artifact")

    assert result.returncode == 0, result.stderr
    for command in (
        "build",
        "recover",
        "rollback-check",
        "invalidate",
        "retire",
        "retirement-preview",
        "cleanup",
        "recover-files",
        "validate",
        "inspect",
    ):
        assert command in result.stdout


def test_collaborative_artifact_subcommand_help_matches_operator_flags() -> None:
    expected_flags = {
        "build": (
            "--source",
            "--output",
            "--fixture",
            "--catalog",
            "--build-id",
            "--confirm-live-build",
        ),
        "recover": ("--artifact", "--build-id", "--confirm-live-recovery"),
        "rollback-check": ("--artifact",),
        "invalidate": ("--build-id", "--confirm-invalidation"),
        "retire": ("--build-id", "--confirm-retirement"),
        "retirement-preview": ("--artifact-set",),
        "cleanup": ("--artifact-set", "--confirm-cleanup"),
        "recover-files": (
            "--artifact-set",
            "--target",
            "--kind",
            "--execute",
            "--confirm-recovery",
            "--writers-stopped",
        ),
        "validate": ("--artifact", "--catalog"),
        "inspect": ("--artifact", "--catalog"),
    }

    for command, flags in expected_flags.items():
        result = _run_help("app.commands.collaborative_artifact", command)
        assert result.returncode == 0, result.stderr
        for flag in flags:
            assert flag in result.stdout


def test_collaborative_snapshot_audit_help_exposes_wrapper_arguments() -> None:
    snapshot_help = _run_help("app.commands.collaborative_snapshot", "audit")
    assert snapshot_help.returncode == 0, snapshot_help.stderr
    for flag in ("--source", "--fixture", "--catalog", "--format"):
        assert flag in snapshot_help.stdout
