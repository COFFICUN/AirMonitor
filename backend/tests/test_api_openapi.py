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
DEVICE_ID_PARAMETER_CONTRACT = (
    "device_id",
    "path",
    True,
    (
        ("description", "Positive device ID"),
        ("exclusiveMinimum", 0),
        ("maximum", POSTGRES_INTEGER_MAX),
        ("title", "Device Id"),
        ("type", "integer"),
    ),
)
NOT_FOUND_RESPONSE = (
    "404",
    "ErrorResponse",
    "The requested device or active session does not exist.",
)
CONFLICT_RESPONSE = (
    "409",
    "ErrorResponse",
    "The requested operation conflicts with domain state.",
)
VALIDATION_RESPONSE = (
    "422",
    "ErrorResponse",
    "The request body, path, or query data is invalid.",
)
INTERNAL_RESPONSE = (
    "500",
    "ErrorResponse",
    "An unexpected internal server error occurred.",
)
CAPTURED_EXISTING_OPERATION_CONTRACTS = {
    ("/health", "get"): (
        "get_health_health_get",
        ("health",),
        (),
        None,
        (("200", "HealthResponse", "Successful Response"),),
    ),
    ("/api/v1/devices", "post"): (
        "create_device",
        ("devices",),
        (),
        ("DeviceCreateRequest", True),
        (
            ("201", "DeviceResponse", "Successful Response"),
            CONFLICT_RESPONSE,
            VALIDATION_RESPONSE,
            INTERNAL_RESPONSE,
        ),
    ),
    ("/api/v1/devices/{device_id}", "get"): (
        "get_device",
        ("devices",),
        (DEVICE_ID_PARAMETER_CONTRACT,),
        None,
        (
            ("200", "DeviceResponse", "Successful Response"),
            NOT_FOUND_RESPONSE,
            VALIDATION_RESPONSE,
            INTERNAL_RESPONSE,
        ),
    ),
    ("/api/v1/devices/{device_id}/status", "patch"): (
        "set_device_status",
        ("devices",),
        (DEVICE_ID_PARAMETER_CONTRACT,),
        ("DeviceStatusRequest", True),
        (
            ("200", "DeviceResponse", "Successful Response"),
            NOT_FOUND_RESPONSE,
            VALIDATION_RESPONSE,
            INTERNAL_RESPONSE,
        ),
    ),
    ("/api/v1/devices/{device_id}/sessions", "post"): (
        "start_measurement_session",
        ("measurement sessions",),
        (DEVICE_ID_PARAMETER_CONTRACT,),
        ("SessionCreateRequest", True),
        (
            ("201", "SessionResponse", "Successful Response"),
            NOT_FOUND_RESPONSE,
            CONFLICT_RESPONSE,
            VALIDATION_RESPONSE,
            INTERNAL_RESPONSE,
        ),
    ),
    ("/api/v1/devices/{device_id}/sessions/active", "get"): (
        "get_active_measurement_session",
        ("measurement sessions",),
        (DEVICE_ID_PARAMETER_CONTRACT,),
        None,
        (
            ("200", "SessionResponse", "Successful Response"),
            NOT_FOUND_RESPONSE,
            VALIDATION_RESPONSE,
            INTERNAL_RESPONSE,
        ),
    ),
    (
        "/api/v1/devices/{device_id}/sessions/active/complete",
        "post",
    ): (
        "complete_active_measurement_session",
        ("measurement sessions",),
        (DEVICE_ID_PARAMETER_CONTRACT,),
        ("SessionTransitionRequest", False),
        (
            ("200", "SessionResponse", "Successful Response"),
            NOT_FOUND_RESPONSE,
            CONFLICT_RESPONSE,
            VALIDATION_RESPONSE,
            INTERNAL_RESPONSE,
        ),
    ),
    (
        "/api/v1/devices/{device_id}/sessions/active/cancel",
        "post",
    ): (
        "cancel_active_measurement_session",
        ("measurement sessions",),
        (DEVICE_ID_PARAMETER_CONTRACT,),
        ("SessionTransitionRequest", False),
        (
            ("200", "SessionResponse", "Successful Response"),
            NOT_FOUND_RESPONSE,
            CONFLICT_RESPONSE,
            VALIDATION_RESPONSE,
            INTERNAL_RESPONSE,
        ),
    ),
    ("/api/v1/devices/{device_id}/measurements", "post"): (
        "record_raw_measurement",
        ("measurements",),
        (DEVICE_ID_PARAMETER_CONTRACT,),
        ("MeasurementCreateRequest", True),
        (
            ("201", "MeasurementResponse", "Successful Response"),
            NOT_FOUND_RESPONSE,
            CONFLICT_RESPONSE,
            VALIDATION_RESPONSE,
            INTERNAL_RESPONSE,
        ),
    ),
}
TELEMETRY_READ_OPERATIONS = {
    ("/api/v1/devices/{device_id}/sessions", "get"): (
        "list_device_sessions",
        "SessionListResponse",
    ),
    ("/api/v1/devices/{device_id}/measurements", "get"): (
        "list_device_measurements",
        "MeasurementListResponse",
    ),
}


def _schema_name(schema: dict[str, object]) -> str:
    reference = schema["$ref"]
    assert isinstance(reference, str)
    return reference.rsplit("/", 1)[-1]


def _operation_contract(
    operation: dict[str, object],
) -> tuple[object, ...]:
    parameters = tuple(
        (
            parameter["name"],
            parameter["in"],
            parameter.get("required", False),
            tuple(sorted(parameter["schema"].items())),
        )
        for parameter in operation.get("parameters", [])
    )
    request_body = operation.get("requestBody")
    if request_body is None:
        request_contract = None
    else:
        request_contract = (
            _schema_name(
                request_body["content"]["application/json"]["schema"]
            ),
            request_body.get("required", False),
        )
    responses = tuple(
        (
            status_code,
            _schema_name(
                response["content"]["application/json"]["schema"]
            ),
            response["description"],
        )
        for status_code, response in operation["responses"].items()
    )
    return (
        operation["operationId"],
        tuple(operation.get("tags", [])),
        parameters,
        request_contract,
        responses,
    )


def _parameter_schema_for_type(
    parameter: dict[str, object],
    expected_type: str,
) -> dict[str, object]:
    schema = parameter["schema"]
    if schema.get("type") == expected_type:
        return schema
    return next(
        variant
        for variant in schema["anyOf"]
        if variant.get("type") == expected_type
    )


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


def test_openapi_generation_is_connection_free_and_preserves_existing_scope(
) -> None:
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
    assert EXPECTED_OPERATIONS <= actual_operations
    assert ("/health", "get") in all_operations
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


def test_existing_nine_openapi_contracts_match_captured_baseline() -> None:
    schema = create_application(Settings(_env_file=None)).openapi()

    assert set(CAPTURED_EXISTING_OPERATION_CONTRACTS) <= {
        (path, method)
        for path, path_item in schema["paths"].items()
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    for key, expected_contract in (
        CAPTURED_EXISTING_OPERATION_CONTRACTS.items()
    ):
        path, method = key
        assert _operation_contract(
            schema["paths"][path][method]
        ) == expected_contract


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


def test_telemetry_read_openapi_inventory_and_operation_ids() -> None:
    schema = create_application(Settings(_env_file=None)).openapi()
    operations = {
        (path, method): operation
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }

    assert schema["openapi"] == "3.1.0"
    assert len(operations) == 11
    assert sum(
        path.startswith("/api/v1") for path, _ in operations
    ) == 10
    assert sum(path == "/health" for path, _ in operations) == 1
    operation_ids = [
        operation["operationId"] for operation in operations.values()
    ]
    assert len(operation_ids) == 11
    assert len(set(operation_ids)) == 11
    for key, (operation_id, _) in TELEMETRY_READ_OPERATIONS.items():
        assert operations[key]["operationId"] == operation_id


def test_telemetry_read_openapi_uses_concrete_responses_and_exact_errors(
) -> None:
    schema = create_application(Settings(_env_file=None)).openapi()

    for (
        path,
        method,
    ), (
        _,
        response_schema_name,
    ) in TELEMETRY_READ_OPERATIONS.items():
        operation = schema["paths"][path][method]
        assert set(operation["responses"]) == {"200", "404", "422", "500"}
        assert _schema_name(
            operation["responses"]["200"]["content"][
                "application/json"
            ]["schema"]
        ) == response_schema_name
        for status_code in ("404", "422", "500"):
            assert _schema_name(
                operation["responses"][status_code]["content"][
                    "application/json"
                ]["schema"]
            ) == "ErrorResponse"
        assert operation["responses"]["500"]["description"] == (
            "An unexpected internal server error occurred."
        )

        response_component = schema["components"]["schemas"][
            response_schema_name
        ]
        assert set(response_component["required"]) == {
            "items",
            "next_cursor",
        }
        assert set(response_component["properties"]) == {
            "items",
            "next_cursor",
        }


def test_telemetry_read_openapi_session_query_contract() -> None:
    schema = create_application(Settings(_env_file=None)).openapi()
    operation = schema["paths"][
        "/api/v1/devices/{device_id}/sessions"
    ]["get"]
    parameters = {
        parameter["name"]: parameter
        for parameter in operation["parameters"]
    }

    assert set(parameters) == {
        "device_id",
        "status",
        "started_from",
        "started_to",
        "limit",
        "cursor",
    }
    device_schema = parameters["device_id"]["schema"]
    assert device_schema["type"] == "integer"
    assert device_schema["exclusiveMinimum"] == 0
    assert device_schema["maximum"] == POSTGRES_INTEGER_MAX
    status_schema = _parameter_schema_for_type(
        parameters["status"],
        "string",
    )
    assert set(status_schema["enum"]) == {
        "active",
        "completed",
        "cancelled",
    }
    for parameter_name in ("started_from", "started_to"):
        timestamp_schema = _parameter_schema_for_type(
            parameters[parameter_name],
            "string",
        )
        assert timestamp_schema["format"] == "date-time"
    limit_schema = parameters["limit"]["schema"]
    assert limit_schema["type"] == "integer"
    assert limit_schema["default"] == 100
    assert limit_schema["minimum"] == 1
    assert limit_schema["maximum"] == 500
    cursor_schema = _parameter_schema_for_type(
        parameters["cursor"],
        "string",
    )
    assert cursor_schema["maxLength"] == 2_048


def test_telemetry_read_openapi_measurement_query_contract() -> None:
    schema = create_application(Settings(_env_file=None)).openapi()
    operation = schema["paths"][
        "/api/v1/devices/{device_id}/measurements"
    ]["get"]
    parameters = {
        parameter["name"]: parameter
        for parameter in operation["parameters"]
    }

    assert set(parameters) == {
        "device_id",
        "session_id",
        "measured_from",
        "measured_to",
        "limit",
        "cursor",
    }
    device_schema = parameters["device_id"]["schema"]
    assert device_schema["type"] == "integer"
    assert device_schema["exclusiveMinimum"] == 0
    assert device_schema["maximum"] == POSTGRES_INTEGER_MAX
    session_schema = _parameter_schema_for_type(
        parameters["session_id"],
        "integer",
    )
    assert session_schema["exclusiveMinimum"] == 0
    assert session_schema["maximum"] == POSTGRES_INTEGER_MAX
    for parameter_name in ("measured_from", "measured_to"):
        timestamp_schema = _parameter_schema_for_type(
            parameters[parameter_name],
            "string",
        )
        assert timestamp_schema["format"] == "date-time"
    limit_schema = parameters["limit"]["schema"]
    assert limit_schema["type"] == "integer"
    assert limit_schema["default"] == 100
    assert limit_schema["minimum"] == 1
    assert limit_schema["maximum"] == 500
    cursor_schema = _parameter_schema_for_type(
        parameters["cursor"],
        "string",
    )
    assert cursor_schema["maxLength"] == 2_048
