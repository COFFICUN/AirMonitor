"""Static contracts for the production-readiness repository layer."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
DOCKERFILE = BACKEND_ROOT / "Dockerfile"
DOCKERIGNORE = BACKEND_ROOT / ".dockerignore"
ENTRYPOINT = BACKEND_ROOT / "docker-entrypoint.sh"
COMPOSE_FILE = REPOSITORY_ROOT / "compose.yaml"
WORKFLOW_FILE = (
    REPOSITORY_ROOT / ".github" / "workflows" / "backend-ci.yml"
)
ROOT_ENV_EXAMPLE = REPOSITORY_ROOT / ".env.example"
BACKEND_ENV_EXAMPLE = BACKEND_ROOT / ".env.example"


def _required_text(path: Path) -> str:
    assert path.is_file(), f"required repository file is missing: {path.name}"
    return path.read_text(encoding="utf-8")


def _yaml_mapping(path: Path, *, base_loader: bool = False) -> dict[str, Any]:
    source = _required_text(path)
    loader = yaml.BaseLoader if base_loader else yaml.SafeLoader
    document = yaml.load(source, Loader=loader)
    assert isinstance(document, dict)
    return document


def _dockerfile_instructions(source: str) -> list[tuple[str, str]]:
    logical_lines: list[str] = []
    pending = ""
    for physical_line in source.splitlines():
        stripped = physical_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pending = f"{pending} {stripped}".strip()
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        logical_lines.append(pending)
        pending = ""
    assert pending == ""

    instructions: list[tuple[str, str]] = []
    for line in logical_lines:
        instruction, separator, argument = line.partition(" ")
        assert separator, f"invalid Dockerfile instruction: {line}"
        instructions.append((instruction.upper(), argument.strip()))
    return instructions


def _workflow_run_commands(workflow: dict[str, Any]) -> list[str]:
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    commands: list[str] = []
    for job in jobs.values():
        assert isinstance(job, dict)
        steps = job.get("steps", [])
        assert isinstance(steps, list)
        for step in steps:
            assert isinstance(step, dict)
            command = step.get("run")
            if isinstance(command, str):
                commands.append(command)
    return commands


def test_dockerfile_defines_minimal_non_root_python_313_runtime() -> None:
    source = _required_text(DOCKERFILE)
    instructions = _dockerfile_instructions(source)
    by_name: dict[str, list[str]] = {}
    for name, argument in instructions:
        by_name.setdefault(name, []).append(argument)

    assert len(by_name.get("FROM", [])) == 1
    base_image = by_name["FROM"][0].casefold()
    assert base_image.startswith("python:3.13")
    assert "slim" in base_image

    assert by_name.get("WORKDIR") == ["/app"]
    assert "PYTHONDONTWRITEBYTECODE=1" in source
    assert "PYTHONUNBUFFERED=1" in source
    assert by_name.get("EXPOSE") == ["8000"]

    assert "requirements.txt" in source
    assert "requirements-dev.txt" not in source
    assert "COPY . " not in source
    assert "COPY tests" not in source
    assert ".venv" not in source
    assert any("app" in value for value in by_name.get("COPY", []))
    assert any("alembic" in value for value in by_name.get("COPY", []))
    assert any("alembic.ini" in value for value in by_name.get("COPY", []))

    runtime_users = by_name.get("USER", [])
    assert runtime_users
    assert runtime_users[-1].casefold() not in {"0", "root"}
    assert by_name.get("ENTRYPOINT") == ['["/app/docker-entrypoint.sh"]']


def test_dockerignore_excludes_local_and_secret_artifacts() -> None:
    patterns = {
        line.strip()
        for line in _required_text(DOCKERIGNORE).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    required_patterns = {
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".coverage",
        "htmlcov",
        ".env",
        "*.db",
        "*.sqlite",
        "*.pem",
        "*.key",
        ".git",
        ".vscode",
        ".idea",
        "dist",
        "build",
        "tests",
    }
    assert required_patterns <= patterns


def test_entrypoint_is_lf_bounded_migration_first_and_execs_api() -> None:
    assert ENTRYPOINT.is_file()
    source_bytes = ENTRYPOINT.read_bytes()
    assert source_bytes.startswith(b"#!/bin/sh\n")
    assert b"\r" not in source_bytes
    source = source_bytes.decode("utf-8")

    assert "set -eu" in source
    assert "set -x" not in source
    assert "asyncpg.connect" in source
    assert "while true" not in source.casefold()
    assert re.search(r"range\(1,\s*\d+\)", source)
    assert "Database readiness check timed out." in source

    migration_position = source.index("alembic upgrade head")
    exec_match = re.search(
        r"exec\s+python\s+-m\s+uvicorn\s+app\.main:app",
        source,
    )
    assert exec_match is not None
    assert migration_position < exec_match.start()


def test_compose_defines_isolated_healthy_api_and_postgresql_services() -> None:
    compose = _yaml_mapping(COMPOSE_FILE)
    services = compose.get("services")
    volumes = compose.get("volumes")
    assert isinstance(services, dict)
    assert isinstance(volumes, dict)
    assert {"api", "db"} <= services.keys()

    database = services["db"]
    assert isinstance(database, dict)
    assert str(database.get("image", "")).startswith("postgres:18")
    assert database.get("ports") in (None, [])
    assert database.get("restart") == "unless-stopped"
    database_health = database.get("healthcheck")
    assert isinstance(database_health, dict)
    assert "pg_isready" in " ".join(database_health.get("test", []))

    database_mounts = database.get("volumes")
    assert isinstance(database_mounts, list)
    named_mounts = [str(mount).split(":", 1)[0] for mount in database_mounts]
    assert named_mounts
    assert all(name in volumes for name in named_mounts)

    database_environment = database.get("environment")
    assert isinstance(database_environment, dict)
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        value = database_environment.get(name)
        assert isinstance(value, str)
        assert value.startswith("${")

    api = services["api"]
    assert isinstance(api, dict)
    assert api.get("privileged") in (None, False)
    assert api.get("restart") == "unless-stopped"
    build = api.get("build")
    assert build == "./backend" or (
        isinstance(build, dict) and build.get("context") == "./backend"
    )

    dependency = api.get("depends_on")
    assert isinstance(dependency, dict)
    assert dependency.get("db", {}).get("condition") == "service_healthy"

    api_environment = api.get("environment")
    assert isinstance(api_environment, dict)
    assert "@db:5432/" in api_environment["AIRMONITOR_DATABASE_URL"]
    assert api_environment["AIRMONITOR_ENVIRONMENT"] == "development"
    assert api_environment["UVICORN_HOST"] == "0.0.0.0"
    assert api_environment["UVICORN_PORT"] == "8000"

    published_ports = api.get("ports")
    assert isinstance(published_ports, list)
    assert len(published_ports) == 1
    assert str(published_ports[0]).endswith(":8000")

    api_health = api.get("healthcheck")
    assert isinstance(api_health, dict)
    assert "/health" in " ".join(api_health.get("test", []))


def test_environment_examples_are_placeholders_and_real_env_is_ignored() -> None:
    root_example = _required_text(ROOT_ENV_EXAMPLE)
    backend_example = _required_text(BACKEND_ENV_EXAMPLE)
    ignore_source = _required_text(REPOSITORY_ROOT / ".gitignore")

    assert "POSTGRES_DB=" in root_example
    assert "POSTGRES_USER=" in root_example
    password_line = next(
        line for line in root_example.splitlines()
        if line.startswith("POSTGRES_PASSWORD=")
    )
    assert any(marker in password_line.casefold() for marker in ("replace", "change", "<"))

    database_line = next(
        line for line in backend_example.splitlines()
        if line.startswith("AIRMONITOR_DATABASE_URL=")
    )
    assert "<username>" in database_line
    assert "<password>" in database_line
    assert "<database>" in database_line

    combined_examples = f"{root_example}\n{backend_example}"
    assert "C:\\Users\\" not in combined_examples
    assert "BEGIN PRIVATE KEY" not in combined_examples
    assert ".env" in ignore_source
    assert "!.env.example" in ignore_source


def test_shell_files_are_forced_to_lf_by_repository_attributes() -> None:
    attributes = _required_text(REPOSITORY_ROOT / ".gitattributes")
    assert "*.sh text eol=lf" in attributes


def test_backend_ci_has_offline_postgresql_and_docker_gates() -> None:
    workflow = _yaml_mapping(WORKFLOW_FILE, base_loader=True)
    assert workflow.get("permissions") == {"contents": "read"}

    triggers = workflow.get("on")
    assert isinstance(triggers, dict)
    assert "pull_request" in triggers
    assert triggers.get("push", {}).get("branches") == ["develop"]

    concurrency = workflow.get("concurrency")
    assert isinstance(concurrency, dict)
    assert concurrency.get("cancel-in-progress") == "true"

    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    assert {"offline", "postgresql", "docker"} <= jobs.keys()

    offline = jobs["offline"]
    offline_environment = offline.get("env")
    assert isinstance(offline_environment, dict)
    for variable in (
        "AIRMONITOR_DATABASE_URL",
        "AIRMONITOR_RUN_PERSISTENCE_INTEGRATION",
        "AIRMONITOR_TEST_DATABASE_URL",
        "AIRMONITOR_API_TEST_DATABASE_URL",
    ):
        assert offline_environment.get(variable) == ""

    postgresql = jobs["postgresql"]
    services = postgresql.get("services")
    assert isinstance(services, dict)
    database_service = services.get("postgres")
    assert isinstance(database_service, dict)
    assert str(database_service.get("image", "")).startswith("postgres:18")
    service_environment = database_service.get("env")
    assert isinstance(service_environment, dict)
    database_name = service_environment.get("POSTGRES_DB")
    assert isinstance(database_name, str)
    assert database_name.startswith("airmonitor_api_test_")
    assert database_name != "airmonitor"
    assert "pg_isready" in database_service.get("options", "")

    docker_commands = "\n".join(
        command
        for command in _workflow_run_commands(
            {"jobs": {"docker": jobs["docker"]}}
        )
    )
    assert "docker build" in docker_commands
    assert "docker image inspect" in docker_commands


def test_every_ci_pytest_command_has_required_safety_flags() -> None:
    workflow = _yaml_mapping(WORKFLOW_FILE, base_loader=True)
    pytest_lines = [
        line.strip()
        for command in _workflow_run_commands(workflow)
        for line in command.splitlines()
        if "pytest" in line and not line.lstrip().startswith("#")
    ]
    assert pytest_lines
    assert all(" -B " in f" {line} " for line in pytest_lines)
    assert all("-p no:cacheprovider" in line for line in pytest_lines)


def test_ci_uses_only_official_pinned_actions_and_does_not_echo_secrets() -> None:
    source = _required_text(WORKFLOW_FILE)
    workflow = _yaml_mapping(WORKFLOW_FILE, base_loader=True)
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)

    uses_values = [
        step["uses"]
        for job in jobs.values()
        for step in job.get("steps", [])
        if isinstance(step, dict) and "uses" in step
    ]
    assert uses_values
    assert set(uses_values) == {
        "actions/checkout@v7",
        "actions/setup-node@v6",
        "actions/setup-python@v7",
        "actions/upload-artifact@v7",
    }
    assert all(
        re.fullmatch(
            r"actions/(checkout|setup-node|setup-python|upload-artifact)@v\d+",
            value,
        )
        for value in uses_values
    )
    assert "secrets." not in source
    assert not re.search(
        r"echo\s+.*(?:PASSWORD|DATABASE_URL)",
        source,
        flags=re.IGNORECASE,
    )


def test_readme_commands_match_canonical_files_services_and_urls() -> None:
    readme = _required_text(REPOSITORY_ROOT / "README.md")
    for required_text in (
        "compose.yaml",
        "docker compose up --build",
        "docker compose down",
        "backend/Dockerfile",
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8000/openapi.json",
        "a75caa2b44f5",
    ):
        assert required_text in readme
