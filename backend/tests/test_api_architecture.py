"""Static boundary checks for the Sprint 7 API layer."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
ENDPOINT_DIRECTORY = BACKEND_DIRECTORY / "app" / "api" / "v1" / "endpoints"
QUERY_SERVICE_PATH = BACKEND_DIRECTORY / "app" / "services" / "queries.py"
FORBIDDEN_ROUTE_CALLS = {
    "begin",
    "begin_nested",
    "commit",
    "execute",
    "flush",
    "rollback",
}


def _imports(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_route_sources_do_not_cross_persistence_boundaries() -> None:
    endpoint_files = sorted(ENDPOINT_DIRECTORY.glob("*.py"))
    assert endpoint_files

    violations: list[str] = []
    for endpoint_file in endpoint_files:
        tree = ast.parse(endpoint_file.read_text(encoding="utf-8"))
        imported = _imports(tree)
        if any(
            module == "sqlalchemy" or module.startswith("sqlalchemy.")
            for module in imported
        ):
            violations.append(f"{endpoint_file.name}:sqlalchemy import")
        if any(
            module == "app.repositories"
            or module.startswith("app.repositories.")
            for module in imported
        ):
            violations.append(f"{endpoint_file.name}:repository import")

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in FORBIDDEN_ROUTE_CALLS
            ):
                violations.append(
                    f"{endpoint_file.name}:{node.lineno}:{node.func.attr}"
                )
            if (
                isinstance(node, ast.ExceptHandler)
                and (
                    node.type is None
                    or isinstance(node.type, ast.Name)
                    and node.type.id in {"Exception", "BaseException"}
                )
            ):
                violations.append(
                    f"{endpoint_file.name}:{node.lineno}:broad catch"
                )

    assert violations == []


def test_query_services_use_repositories_without_write_operations() -> None:
    tree = ast.parse(QUERY_SERVICE_PATH.read_text(encoding="utf-8"))
    forbidden_calls = {
        "begin",
        "begin_nested",
        "commit",
        "flush",
        "rollback",
    }
    violations = [
        f"{node.lineno}:{node.func.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden_calls
    ]

    assert violations == []
    assert all(
        "for_update" not in node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    )


def test_application_import_does_not_connect_or_create_schema() -> None:
    script = dedent(
        """
        from contextlib import ExitStack
        from importlib import import_module
        from unittest.mock import patch

        targets = (
            "asyncpg.connect",
            "sqlalchemy.engine.Engine.connect",
            "sqlalchemy.ext.asyncio.AsyncEngine.connect",
            "sqlalchemy.sql.schema.MetaData.create_all",
        )
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch(target)) for target in targets]
            module = import_module("app.main")
            module.app.openapi()

        called = [
            target
            for target, mock in zip(targets, mocks, strict=True)
            if mock.called
        ]
        if called:
            raise AssertionError(called)
        """
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
