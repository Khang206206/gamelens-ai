"""Explicit Phase 8 combined gate. Run from the repository root with Python 3.12+."""

import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "tmp" / f"phase8-{time.time_ns()}"
RECORD.mkdir(parents=True)
os.chdir(ROOT)
os.environ["MSYS_NO_PATHCONV"] = "1"
results = []


def run(name, args, expected=0):
    started = time.monotonic()
    print(f"START {name}", flush=True)
    path = RECORD / f"{name}.log"
    with path.open("w", encoding="utf-8") as output:
        completed = subprocess.run(args, stdout=output, stderr=subprocess.STDOUT, check=False)
    text = path.read_text(encoding="utf-8", errors="replace")
    # No expanded environment/config, private browser state or raw failure reports retained.
    private = re.search(
        r'(?i)(postgresql(?:\+psycopg)?://|"(?:anonymous_token(?:_digest)?|user_id|'
        r'cohort_mapping|session_token)"\s*:|set-cookie:|x-csrf-token:\s*\S)',
        text,
    )
    results.append(
        {
            "name": name,
            "command": args,
            "exit_code": completed.returncode,
            "expected_exit": expected,
            "seconds": round(time.monotonic() - started, 2),
            "privacy_scan": "failed" if private else "passed",
        }
    )
    (RECORD / "commands.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"END {name}: exit={completed.returncode}, seconds={results[-1]['seconds']}", flush=True)
    if private:
        raise RuntimeError(f"Private output found in {name}; do not publish logs")
    if completed.returncode != expected:
        raise RuntimeError(f"{name} failed; inspect {path}")
    return text


def compose(project, file):
    return ["docker", "compose", "--project-name", project, "--file", file]


def runtime_audit(prefix, project):
    for service in ("e2e-api", "e2e-web"):
        container = subprocess.check_output(prefix + ["ps", "--quiet", service], text=True).strip()
        # Select safe fields in Docker, so secret-valued environment is never collected.
        info = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "inspect",
                    container,
                    "--format",
                    '{"mounts":{{json .Mounts}},"privileged":{{json .HostConfig.Privileged}}}',
                ],
                text=True,
            )
        )
        assert not info["privileged"]
        for mount in info["mounts"]:
            assert mount["Type"] == "volume"
            labels = json.loads(
                subprocess.check_output(
                    [
                        "docker",
                        "volume",
                        "inspect",
                        mount["Name"],
                        "--format",
                        "{{json .Labels}}",
                    ],
                    text=True,
                )
            )
            assert labels["com.docker.compose.project"] == project
            if service == "e2e-api":
                assert not mount["RW"]
        language = "python" if service == "e2e-api" else "node"
        code = (
            "from pathlib import Path; import json; "
            "uid=Path('/proc/1/status').read_text().split('Uid:')[1].split()[0]; "
            "assert int(uid)>0; "
            "assert not any(p.name == '.env' or p.suffix in ('.key','.pem') "
            "for p in Path('/workspace').rglob('*')); "
            "assert not Path('/workspace/data/external').exists(); "
            "assert not Path('/workspace/ml/artifacts').exists(); "
            "print(json.dumps({'runtime_uid':int(uid),'image_privacy':'passed'}))"
            if language == "python"
            else "const fs=require('fs'); const uid=+fs.readFileSync('/proc/1/status','utf8')"
            ".split('Uid:')[1].trim().split(/\\s/)[0];"
            "if(!uid)process.exit(1); console.log(JSON.stringify({runtime_uid:uid}));"
        )
        run(
            service + "-runtime",
            prefix
            + ["exec", "--no-TTY", service, language, "-c" if language == "python" else "-e", code],
        )


def remove_project(prefix, project):
    # Ownership records include only labels/IDs, never inspect environment.
    for kind in ("container", "network", "volume"):
        run(
            f"{project}-{kind}-ownership",
            [
                "docker",
                kind,
                "ls",
                *(["--all"] if kind == "container" else []),
                "--filter",
                f"label=com.docker.compose.project={project}",
                "--quiet",
            ],
        )
    run(f"{project}-down", prefix + ["down", "--volumes", "--remove-orphans"])
    for kind in ("container", "network", "volume"):
        remaining = run(
            f"{project}-{kind}-removed",
            [
                "docker",
                kind,
                "ls",
                *(["--all"] if kind == "container" else []),
                "--filter",
                f"label=com.docker.compose.project={project}",
                "--quiet",
            ],
        )
        if remaining.strip():
            raise RuntimeError("Project teardown left resources")


def main():
    (RECORD / "host.json").write_text(
        json.dumps(
            {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "tested_revision": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], text=True
                ).strip(),
                "note": "working tree implementation; synthetic test data only",
            },
            indent=2,
        )
        + "\n"
    )
    run("docker-version", ["docker", "version", "--format", "{{json .}}"])
    run("compose-version", ["docker", "compose", "version"])
    run(
        "docker-host",
        ["docker", "info", "--format", "{{.OSType}} {{.OperatingSystem}} {{.Architecture}}"],
    )
    run(
        "root-config",
        [
            "docker",
            "compose",
            "--profile",
            "model",
            "--profile",
            "quality",
            "--profile",
            "source-audit",
            "config",
            "--quiet",
        ],
    )
    run(
        "test-config",
        ["docker", "compose", "-f", "infra/docker-compose.test.yml", "config", "--quiet"],
    )
    for profile in (None, "fixture", "fallback", "live-source", "lifecycle"):
        args = ["docker", "compose", "-f", "infra/docker-compose.e2e.yml"]
        if profile:
            args += ["--profile", profile]
        if profile == "fallback":
            args += ["--profile", "fixture"]
        run(f"config-{profile or 'content'}", args + ["config", "--quiet"])
    quality = [
        "docker",
        "compose",
        "run",
        "--build",
        "--rm",
        "--no-deps",
        "quality",
        "python",
        "-m",
    ]
    for name, args in (
        ("api-unit", ["pytest", "tests/unit", "-q", "-p", "no:cacheprovider"]),
        ("ml", ["pytest", "/workspace/ml/tests", "-q", "-p", "no:cacheprovider"]),
        (
            "ruff",
            [
                "ruff",
                "check",
                "--no-cache",
                "app",
                "tests",
                "alembic",
                "/workspace/ml/src",
                "/workspace/ml/tests",
            ],
        ),
        (
            "ruff-format",
            [
                "ruff",
                "format",
                "--no-cache",
                "--check",
                "app",
                "tests",
                "alembic",
                "/workspace/ml/src",
                "/workspace/ml/tests",
            ],
        ),
    ):
        run(name, quality + args)
    project = f"gamelens-ai-e2e-integration-{os.getpid()}"
    prefix = compose(project, "infra/docker-compose.test.yml")
    try:
        run("postgresql", prefix + ["run", "--build", "--rm", "test-api"])
    finally:
        remove_project(prefix, project)
    project = f"gamelens-ai-e2e-content-{os.getpid()}"
    prefix = compose(project, "infra/docker-compose.e2e.yml")
    try:
        run("content-build", prefix + ["build", "e2e-setup", "e2e-web", "e2e"])
        run("content-up", prefix + ["up", "--detach", "--wait", "e2e-web"])
        runtime_audit(prefix, project)
        run("api-python", prefix + ["exec", "--no-TTY", "e2e-api", "python", "--version"])
        run("web-node", prefix + ["exec", "--no-TTY", "e2e-web", "node", "--version"])
        run("web-npm", prefix + ["exec", "--no-TTY", "e2e-web", "npm", "--version"])
        run("postgres-version", prefix + ["exec", "--no-TTY", "test-db", "postgres", "--version"])
        run(
            "migration-head",
            prefix + ["exec", "--no-TTY", "e2e-api", "python", "-m", "alembic", "current"],
        )
        run("stage1-4-e2e", prefix + ["run", "--rm", "--no-deps", "e2e"])
        for script in ("typecheck", "lint", "format:check", "test", "build", "api:types:check"):
            run(
                "web-" + script.replace(":", "-"),
                prefix
                + [
                    "run",
                    "--rm",
                    "--no-deps",
                    "-e",
                    "NEXT_PUBLIC_API_URL=http://gamelens.test:8000",
                    "-e",
                    "NEXT_PUBLIC_CONSENT_VERSION=stage-4-v1",
                    "e2e",
                    "npm",
                    "run",
                    script,
                ],
            )
    finally:
        remove_project(prefix, project)
    for mode, expected in (
        ("pass", 0),
        ("setup", 41),
        ("validation", 1),
        ("browser", 1),
        ("interrupt", 130),
    ):
        fault = run("teardown-" + mode, ["sh", "infra/run-e2e-teardown-probe.sh", mode], expected)
        assert "E2E ownership project=" in fault and "E2E teardown verified project=" in fault
        if mode == "validation":
            assert "Configured artifact directory is missing" in fault
        if mode == "browser":
            assert (
                "injected teardown failure" in fault and "expect(received).toBe(expected)" in fault
            )
    # Fixture runner itself replays twice; replay live and all lifecycle scenarios.
    run("fixture", ["sh", "infra/run-e2e-fixture.sh"])
    replay_values = []
    for replay in (1, 2):
        live = run(f"live-{replay}", ["sh", "infra/run-e2e-live-source.sh"])
        lifecycle = run(f"lifecycle-{replay}", ["sh", "infra/run-e2e-lifecycle.sh"])
        ordering = re.findall(r'"semantic_ordering_sha256": "([a-f0-9]{64})"', live)
        events = re.findall(r'"events_verified": (\d+)', lifecycle)
        assert len(ordering) == 1 and len(events) == 6
        replay_values.append({"live_ordering": ordering, "lifecycle_events": events})
    assert replay_values[0] == replay_values[1], "Clean replay semantic evidence changed"
    (RECORD / "replay.json").write_text(json.dumps(replay_values, indent=2) + "\n")
    run(
        "images",
        [
            "docker",
            "image",
            "inspect",
            "gamelens-ai-api:e2e",
            "gamelens-ai-web:e2e",
            "gamelens-ai-playwright:stage4",
            "--format",
            "{{.Id}} {{json .RepoDigests}}",
        ],
    )
    run("diff-check", ["git", "diff", "--check"])
    print(f"Phase 8 gate passed. Evidence: {RECORD}", flush=True)


if __name__ == "__main__":
    main()
