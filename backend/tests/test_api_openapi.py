"""Connection-free OpenAPI contract verification."""

from contextlib import ExitStack
from unittest.mock import patch

import pytest

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
POSTGRES_INTEGER_MAX = 2_147_483_647
PARTICLE_COUNTER_FIELDS = {
    "pc0_3",
    "pc0_5",
    "pc1_0",
    "pc2_5",
    "pc5_0",
    "pc10",
}
EXPECTED_OPERATION_CONTRACTS = {
    ("/api/v1/devices", "post"): (
        "create_device",
        "201",
        "DeviceResponse",
        "DeviceCreateRequest",
    ),
    ("/api/v1/devices/{device_id}", "get"): (
        "get_device",
        "200",
        "DeviceResponse",
        None,
    ),
    ("/api/v1/devices/{device_id}/status", "patch"): (
        "set_device_status",
        "200",
        "DeviceResponse",
        "DeviceStatusRequest",
    ),
    ("/api/v1/devices/{device_id}/sessions", "post"): (
        "start_measurement_session",
        "201",
        "SessionResponse",
        "SessionCreateRequest",
    ),
    ("/api/v1/devices/{device_id}/sessions/active", "get"): (
        "get_active_measurement_session",
        "200",
        "SessionResponse",
        None,
    ),
    (
        "/api/v1/devices/{device_id}/sessions/active/complete",
        "post",
    ): (
        "complete_active_measurement_session",
        "200",
        "SessionResponse",
        "SessionTransitionRequest",
    ),
    (
        "/api/v1/devices/{device_id}/sessions/active/cancel",
        "post",
    ): (
        "cancel_active_measurement_session",
        "200",
        "SessionResponse",
        "SessionTransitionRequest",
    ),
    ("/api/v1/devices/{device_id}/measurements", "post"): (
        "record_raw_measurement",
        "201",
        "MeasurementResponse",
        "MeasurementCreateRequest",
    ),
}


def test_stale_api_prefix_environment_variable_preserves_openapi_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AIRMONITOR_API_PREFIX", raising=False)
    baseline_schema = create_application(Settings(_env_file=None)).openapi()
    monkeypatch.setenv(
        "AIRMONITOR_API_PREFIX",
        "/phase-c4a-stale-prefix",
    )

    stale_settings = Settings(_env_file=None)
    stale_schema = create_application(stale_settings).openapi()

    assert "api_prefix" not in Settings.model_fields
    assert "api_prefix" not in stale_settings.model_dump()
    assert stale_schema == baseline_schema


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

    all_operations = {
        (path, method)
        for path, path_item in schema["paths"].items()
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    actual_operations = {
        operation
        for operation in all_operations
        if operation[0].startswith("/api/v1")
    }
    assert len(all_operations) == 9
    assert len(actual_operations) == 8
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
        ("/api/v1/devices", "post"): {"201", "409", "422", "500"},
        ("/api/v1/devices/{device_id}", "get"): {
            "200",
            "404",
            "422",
            "500",
        },
        (
            "/api/v1/devices/{device_id}/status",
            "patch",
        ): {"200", "404", "422", "500"},
        (
            "/api/v1/devices/{device_id}/sessions",
            "post",
        ): {"201", "404", "409", "422", "500"},
        (
            "/api/v1/devices/{device_id}/sessions/active",
            "get",
        ): {"200", "404", "422", "500"},
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
        assert operation["responses"]["500"]["description"] == (
            "An unexpected internal server error occurred."
        )


def test_openapi_preserves_exact_public_operation_contracts() -> None:
    schema = create_application(Settings(_env_file=None)).openapi()

    for (
        path,
        method,
    ), (
        operation_id,
        success_code,
        success_schema_name,
        request_schema_name,
    ) in EXPECTED_OPERATION_CONTRACTS.items():
        operation = schema["paths"][path][method]
        assert operation["operationId"] == operation_id
        assert {
            code for code in operation["responses"] if code.startswith("2")
        } == {success_code}
        success_schema = operation["responses"][success_code]["content"][
            "application/json"
        ]["schema"]
        assert success_schema["$ref"].endswith(
            f"/{success_schema_name}"
        )

        request_body = operation.get("requestBody")
        if request_schema_name is None:
            assert request_body is None
        else:
            assert request_body["content"]["application/json"]["schema"][
                "$ref"
            ].endswith(f"/{request_schema_name}")


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


def test_openapi_exposes_postgres_integer_max_for_paths_and_particle_counters() -> None:
    schema = create_application(Settings(_env_file=None)).openapi()

    for path, method in EXPECTED_OPERATIONS:
        if "{device_id}" not in path:
            continue
        device_id_parameter = next(
            parameter
            for parameter in schema["paths"][path][method]["parameters"]
            if parameter["name"] == "device_id"
        )
        assert device_id_parameter["schema"]["maximum"] == (
            POSTGRES_INTEGER_MAX
        )
        assert device_id_parameter["schema"]["exclusiveMinimum"] == 0

    measurement_request = schema["components"]["schemas"][
        "MeasurementCreateRequest"
    ]
    for field_name in PARTICLE_COUNTER_FIELDS:
        field_schema = measurement_request["properties"][field_name]
        integer_schema = next(
            variant
            for variant in field_schema["anyOf"]
            if variant.get("type") == "integer"
        )
        assert integer_schema["minimum"] == 0
        assert integer_schema["maximum"] == POSTGRES_INTEGER_MAX
