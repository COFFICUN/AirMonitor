"""Connection-free OpenAPI contract verification."""

from contextlib import ExitStack
from unittest.mock import patch

from app.core.config import Settings
from app.main import create_application


EXPECTED_OPERATIONS = {
    ("/api/v1/devices", "post"),
    ("/api/v1/devices/{device_id}", "get"),
    ("/api/v1/devices/{device_id}/status", "patch"),
    ("/api/v1/devices/{device_id}/sessions", "post"),
    ("/api/v1/devices/{device_id}/sessions/active", "get"),
    (
        "/api/v1/devices/{device_id}/sessions/active/complete",
        "post",
    ),
    (
        "/api/v1/devices/{device_id}/sessions/active/cancel",
        "post",
    ),
    ("/api/v1/devices/{device_id}/measurements", "post"),
}


def test_openapi_generation_is_connection_free_and_covers_exact_scope() -> None:
    connection_targets = (
        "asyncpg.connect",
        "sqlalchemy.engine.Engine.connect",
        "sqlalchemy.ext.asyncio.AsyncEngine.connect",
    )

    with ExitStack() as stack:
        connection_mocks = [
            stack.enter_context(patch(target))
            for target in connection_targets
        ]
        application = create_application(Settings(_env_file=None))
        schema = application.openapi()

    actual_operations = {
        (path, method)
        for path, path_item in schema["paths"].items()
        if path.startswith("/api/v1")
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert actual_operations == EXPECTED_OPERATIONS
    assert "/health" in schema["paths"]
    assert all(not mock.called for mock in connection_mocks)


def test_openapi_operation_ids_are_unique_and_tags_are_meaningful() -> None:
    schema = create_application(Settings(_env_file=None)).openapi()
    operations = [
        operation
        for path, path_item in schema["paths"].items()
        if path.startswith("/api/v1")
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    operation_ids = [operation["operationId"] for operation in operations]

    assert len(operation_ids) == len(set(operation_ids))
    assert all(operation["tags"] for operation in operations)
    assert {tag for operation in operations for tag in operation["tags"]} == {
        "devices",
        "measurement sessions",
        "measurements",
    }


def test_openapi_documents_success_and_expected_error_models() -> None:
    schema = create_application(Settings(_env_file=None)).openapi()

    expected_responses = {
        ("/api/v1/devices", "post"): {"201", "409", "422"},
        ("/api/v1/devices/{device_id}", "get"): {"200", "404", "422"},
        (
            "/api/v1/devices/{device_id}/status",
            "patch",
        ): {"200", "404", "422"},
        (
            "/api/v1/devices/{device_id}/sessions",
            "post",
        ): {"201", "404", "409", "422", "500"},
        (
            "/api/v1/devices/{device_id}/sessions/active",
            "get",
        ): {"200", "404", "422"},
        (
            "/api/v1/devices/{device_id}/sessions/active/complete",
            "post",
        ): {"200", "404", "409", "422", "500"},
        (
            "/api/v1/devices/{device_id}/sessions/active/cancel",
            "post",
        ): {"200", "404", "409", "422", "500"},
        (
            "/api/v1/devices/{device_id}/measurements",
            "post",
        ): {"201", "404", "409", "422", "500"},
    }

    for (path, method), response_codes in expected_responses.items():
        operation = schema["paths"][path][method]
        assert set(operation["responses"]) == response_codes
        for status_code in response_codes - {"200", "201"}:
            response_schema = operation["responses"][status_code]["content"][
                "application/json"
            ]["schema"]
            assert response_schema["$ref"].endswith("/ErrorResponse")


def test_every_operation_declares_a_concrete_success_schema() -> None:
    schema = create_application(Settings(_env_file=None)).openapi()

    for path, method in EXPECTED_OPERATIONS:
        operation = schema["paths"][path][method]
        success_code = "201" if method == "post" and path.endswith(
            ("/devices", "/sessions", "/measurements")
        ) else "200"
        success_schema = operation["responses"][success_code]["content"][
            "application/json"
        ]["schema"]
        assert success_schema["$ref"].split("/")[-1] in {
            "DeviceResponse",
            "SessionResponse",
            "MeasurementResponse",
        }
