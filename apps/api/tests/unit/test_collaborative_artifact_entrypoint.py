import subprocess
import sys


def test_collaborative_artifact_module_starts_in_a_fresh_interpreter() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.commands.collaborative_artifact", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "rollback-check" in result.stdout
    assert "recover-files" in result.stdout
