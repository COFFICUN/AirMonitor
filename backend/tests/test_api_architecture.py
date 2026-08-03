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
    "delete",
    "execute",
    "flush",
    "limit",
    "offset",
    "order_by",
    "rollback",
    "select",
    "where",
}
TELEMETRY_ROUTE_CONTRACTS = {
    "sessions.py": (
        "list_device_sessions",
        "SessionListResponse",
        "strict_session_query_parameters",
        "resolve_session_read_request",
        "get_session_telemetry_query_service",
    ),
    "measurements.py": (
        "list_device_measurements",
        "MeasurementListResponse",
        "strict_measurement_query_parameters",
        "resolve_measurement_read_request",
        "get_measurement_telemetry_query_service",
    ),
}


def _imports(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


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
                and _call_name(node) in (
                    FORBIDDEN_ROUTE_CALLS | {"AsyncSession"}
                )
            ):
                violations.append(
                    (
                        f"{endpoint_file.name}:{node.lineno}:"
                        f"{_call_name(node)}"
                    )
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


def test_telemetry_read_routes_use_concrete_service_boundaries() -> None:
    for endpoint_name, contract in TELEMETRY_ROUTE_CONTRACTS.items():
        (
            function_name,
            response_model,
            strict_dependency,
            resolver,
            service_provider,
        ) = contract
        endpoint_path = ENDPOINT_DIRECTORY / endpoint_name
        tree = ast.parse(endpoint_path.read_text(encoding="utf-8"))
        matching_functions = [
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == function_name
        ]
        assert len(matching_functions) == 1
        route_function = matching_functions[0]
        names = {
            node.id
            for node in ast.walk(route_function)
            if isinstance(node, ast.Name)
        }
        assert {
            response_model,
            strict_dependency,
            resolver,
            service_provider,
        } <= names

        get_decorators = [
            decorator
            for decorator in route_function.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "get"
        ]
        assert len(get_decorators) == 1
        decorator_keywords = {
            keyword.arg: keyword.value
            for keyword in get_decorators[0].keywords
            if keyword.arg is not None
        }
        declared_response_model = decorator_keywords["response_model"]
        assert isinstance(declared_response_model, ast.Name)
        assert declared_response_model.id == response_model

        dependency_targets = {
            call.args[0].id
            for call in ast.walk(route_function)
            if isinstance(call, ast.Call)
            and _call_name(call) == "Depends"
            and call.args
            and isinstance(call.args[0], ast.Name)
        }
        assert dependency_targets == {
            strict_dependency,
            resolver,
            service_provider,
        }

        assert route_function.returns is not None
        return_contract = ast.unparse(route_function.returns)
        assert return_contract == response_model
        assert "Any" not in return_contract
        assert "dict" not in return_contract


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
