import os
import subprocess

import pytest
import yaml
from app.core.config import PROJECT_ROOT


def test_destructive_topology_has_no_host_mounts_socket_or_public_ports() -> None:
    config = yaml.safe_load((PROJECT_ROOT / "infra/docker-compose.e2e.yml").read_text())
    volumes = config["volumes"]
    assert all(not definition for definition in volumes.values())
    for service in config["services"].values():
        assert not service.get("ports")
        assert not service.get("privileged")
        for mount in service.get("volumes", []):
            assert mount.split(":")[0] in volumes
            assert "docker.sock" not in mount
        if "web" in service.get("image", "") or "playwright" in service.get("image", ""):
            assert not any(
                "SECRET" in key or "DATABASE" in key or "PROMOTION" in key
                for key in service.get("environment", {})
            )


def test_normal_startup_has_no_implicit_model_or_lifecycle_command() -> None:
    config = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
    services = config["services"]
    for name in ("api", "web", "db"):
        assert set(services[name].get("depends_on", {})) <= {"api", "db"}
        assert "command" not in services[name]
    for name in ("model-builder", "collaborative-operator"):
        assert services[name]["profiles"] == ["model"]
        assert services[name]["command"][-1] == "--help"


@pytest.mark.parametrize("mode", ["content", "fixture", "live-source", "lifecycle"])
def test_every_runner_uses_shared_ownership_and_signal_cleanup(mode):
    runner = (PROJECT_ROOT / "infra" / f"run-e2e-{mode}.sh").read_text()
    assert ". infra/e2e-ownership.sh" in runner
    assert "trap cleanup EXIT" in runner
    assert "trap handle_signal HUP INT TERM" in runner
    assert "teardown || true" not in runner


@pytest.mark.parametrize("mode", ["fixture", "lifecycle"])
def test_restart_rejoins_shared_api_namespace_before_browser_traffic(mode):
    runner = (PROJECT_ROOT / "infra" / f"run-e2e-{mode}.sh").read_text()
    stop = runner.index(f"compose stop e2e-{mode}-web")
    restart = runner.index(f"compose restart e2e-{mode}-api", stop)
    rejoin = runner.index(
        f"compose up --detach --wait --force-recreate --no-deps e2e-{mode}-web", restart
    )
    web_restart = runner.index(f"compose restart e2e-{mode}-web", rejoin)
    assert stop < restart < rejoin < web_restart


def test_shared_teardown_rejects_leftover_resources():
    helper = PROJECT_ROOT / "infra/e2e-ownership.sh"
    result = subprocess.run(
        [
            "sh",
            "-c",
            f'''
. "{helper}"
project=gamelens-ai-e2e-unit-123
stack_active=1
docker() {{ echo resource; }}
compose() {{ return 0; }}
trap cleanup EXIT
exit 0
''',
        ],
        capture_output=True,
    )
    assert result.returncode == 1


@pytest.mark.parametrize("exit_code", [0, 41, 43, 130])
def test_shared_teardown_preserves_status_and_checks_only_owned_resources(tmp_path, exit_code):
    docker = tmp_path / "docker"
    docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n')
    docker.chmod(0o755)
    calls = tmp_path / "calls"
    helper = PROJECT_ROOT / "infra/e2e-ownership.sh"
    result = subprocess.run(
        [
            "sh",
            "-c",
            f'''
set -eu
. "{helper}"
project=gamelens-ai-e2e-unit-123
stack_active=1
compose() {{ docker compose --project-name "$project" "$@"; }}
trap cleanup EXIT
exit {exit_code}
''',
        ],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "CALLS": str(calls)},
        capture_output=True,
    )
    assert result.returncode == exit_code
    lines = calls.read_text().splitlines()
    assert len(lines) == 7
    assert all("gamelens-ai-e2e-unit-123" in line for line in lines)
    assert lines[3].endswith("down --volumes --remove-orphans")


def test_teardown_refuses_development_and_surfaces_removal_failure(tmp_path):
    helper = PROJECT_ROOT / "infra/e2e-ownership.sh"
    for project in ("gamelens-ai", "gamelens-ai-e2e-unit-123"):
        result = subprocess.run(
            [
                "sh",
                "-c",
                f'''
set -eu
. "{helper}"
project={project}
stack_active=1
docker() {{ return 0; }}
compose() {{ return 9; }}
trap cleanup EXIT
exit 0
''',
            ],
            capture_output=True,
        )
        assert result.returncode == 1


def test_isolation_snapshots_change_when_artifact_bytes_change(tmp_path, monkeypatch):
    from contextlib import contextmanager

    from tests.fixtures import e2e_isolation

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            return self

        def all(self):
            return [("private-contributor", 1)]

    class Engine:
        def connect(self):
            return Connection()

    @contextmanager
    def engine():
        yield None, Engine()

    monkeypatch.setattr(e2e_isolation, "_guarded_engine", engine)
    monkeypatch.setattr(e2e_isolation, "ARTIFACT_SET", tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text("before")
    before = e2e_isolation.snapshot()
    assert "private-contributor" not in str(before)
    path.write_text("after")
    assert before != e2e_isolation.snapshot()
