"""Request-validation and response-serialization contracts for Sprint 7."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.db.models import Device, MeasurementSession, RawMeasurement
from app.schemas.devices import (
    DeviceCreateRequest,
    DeviceResponse,
    DeviceStatusRequest,
)
from app.schemas.measurements import (
    MeasurementCreateRequest,
    MeasurementResponse,
)
from app.schemas.sessions import (
    SessionCreateRequest,
    SessionResponse,
    SessionTransitionRequest,
)
from app.schemas import telemetry as telemetry_schemas


NOW = datetime(2026, 7, 23, 8, 30, tzinfo=UTC)
POSTGRES_INTEGER_MAX = 2_147_483_647
PARTICLE_COUNTER_FIELDS = (
    "pc0_3",
    "pc0_5",
    "pc1_0",
    "pc2_5",
    "pc5_0",
    "pc10",
)
SESSION_RESPONSE_FIELDS = {
    "id",
    "device_id",
    "status",
    "started_at",
    "ended_at",
    "latitude",
    "longitude",
    "sample_count",
    "created_at",
}
MEASUREMENT_RESPONSE_FIELDS = {
    "id",
    "device_id",
    "session_id",
    "source_message_id",
    "measured_at",
    "received_at",
    "temperature",
    "humidity",
    "pm1",
    "pm25",
    "pm10",
    "pc0_3",
    "pc0_5",
    "pc1_0",
    "pc2_5",
    "pc5_0",
    "pc10",
    "latitude",
    "longitude",
    "is_valid",
    "validation_note",
    "created_at",
}
FORBIDDEN_LIST_FIELDS = {
    "count",
    "has_more",
    "metadata",
    "offset",
    "page",
    "total",
}


@pytest.mark.parametrize(
    ("schema", "values"),
    [
        (
            DeviceCreateRequest,
            {"device_uid": "monitor-1", "unexpected": True},
        ),
        (DeviceStatusRequest, {"is_active": True, "unexpected": True}),
        (
            SessionCreateRequest,
            {"latitude": 51.1, "longitude": 71.4, "unexpected": True},
        ),
        (SessionTransitionRequest, {"unexpected": True}),
        (
            MeasurementCreateRequest,
            {
                "measured_at": NOW.isoformat(),
                "unexpected": True,
            },
        ),
    ],
)
def test_request_schemas_forbid_unknown_fields(
    schema: type[object],
    values: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        schema.model_validate(values)


@pytest.mark.parametrize(
    ("values", "field_name"),
    [
        ({"device_uid": "x" * 256}, "device_uid"),
        ({"device_uid": "monitor-1", "name": "x" * 256}, "name"),
        (
            {
                "measured_at": NOW,
                "source_message_id": "x" * 256,
            },
            "source_message_id",
        ),
    ],
)
def test_request_strings_match_orm_length_limits(
    values: dict[str, object],
    field_name: str,
) -> None:
    schema = (
        DeviceCreateRequest
        if "device_uid" in values
        else MeasurementCreateRequest
    )

    with pytest.raises(ValidationError) as raised:
        schema.model_validate(values)

    assert raised.value.errors()[0]["loc"] == (field_name,)


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (-90.0, -180.0),
        (90.0, 180.0),
        (51.1694, 71.4491),
    ],
)
def test_session_coordinates_accept_inclusive_orm_limits(
    latitude: float,
    longitude: float,
) -> None:
    request = SessionCreateRequest(
        latitude=latitude,
        longitude=longitude,
    )

    assert request.latitude == latitude
    assert request.longitude == longitude


@pytest.mark.parametrize(
    ("latitude", "longitude", "field_name"),
    [
        (-90.0001, 0.0, "latitude"),
        (90.0001, 0.0, "latitude"),
        (0.0, -180.0001, "longitude"),
        (0.0, 180.0001, "longitude"),
    ],
)
def test_session_coordinates_reject_values_outside_orm_limits(
    latitude: float,
    longitude: float,
    field_name: str,
) -> None:
    with pytest.raises(ValidationError) as raised:
        SessionCreateRequest(
            latitude=latitude,
            longitude=longitude,
        )

    assert raised.value.errors()[0]["loc"] == (field_name,)


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(51.1694, None), (None, 71.4491)],
)
def test_measurement_coordinates_must_be_supplied_together(
    latitude: float | None,
    longitude: float | None,
) -> None:
    with pytest.raises(
        ValidationError,
        match="latitude and longitude must be supplied together",
    ):
        MeasurementCreateRequest(
            measured_at=NOW,
            latitude=latitude,
            longitude=longitude,
        )


def test_measurement_coordinates_may_both_be_omitted() -> None:
    request = MeasurementCreateRequest(measured_at=NOW)

    assert request.latitude is None
    assert request.longitude is None


def test_measurement_session_id_is_optional_and_bounded() -> None:
    assert MeasurementCreateRequest(measured_at=NOW).session_id is None
    assert (
        MeasurementCreateRequest(
            measured_at=NOW,
            session_id=POSTGRES_INTEGER_MAX,
        ).session_id
        == POSTGRES_INTEGER_MAX
    )

    for invalid_value in (0, POSTGRES_INTEGER_MAX + 1):
        with pytest.raises(ValidationError) as raised:
            MeasurementCreateRequest(
                measured_at=NOW,
                session_id=invalid_value,
            )
        assert raised.value.errors()[0]["loc"] == ("session_id",)


@pytest.mark.parametrize(
    "schema_values",
    [
        (SessionCreateRequest, {"latitude": 0.0, "longitude": 0.0, "started_at": NOW}),
        (SessionTransitionRequest, {"ended_at": NOW}),
        (MeasurementCreateRequest, {"measured_at": NOW}),
    ],
)
def test_request_timestamps_accept_timezone_aware_values(
    schema_values: tuple[type[object], dict[str, object]],
) -> None:
    schema, values = schema_values

    result = schema.model_validate(values)

    timestamp = next(
        value
        for value in result.model_dump().values()
        if isinstance(value, datetime)
    )
    assert timestamp.utcoffset() is not None


@pytest.mark.parametrize(
    ("schema", "values", "field_name"),
    [
        (
            SessionCreateRequest,
            {
                "latitude": 0.0,
                "longitude": 0.0,
                "started_at": datetime(2026, 7, 23, 8, 30),
            },
            "started_at",
        ),
        (
            SessionTransitionRequest,
            {"ended_at": datetime(2026, 7, 23, 8, 30)},
            "ended_at",
        ),
        (
            MeasurementCreateRequest,
            {"measured_at": datetime(2026, 7, 23, 8, 30)},
            "measured_at",
        ),
    ],
)
def test_request_timestamps_reject_naive_values(
    schema: type[object],
    values: dict[str, object],
    field_name: str,
) -> None:
    with pytest.raises(ValidationError) as raised:
        schema.model_validate(values)

    assert raised.value.errors()[0]["loc"] == (field_name,)
    assert "timezone-aware" in raised.value.errors()[0]["msg"]


@pytest.mark.parametrize(
    "field_name",
    ["pm1", "pm25", "pm10", "pc0_3", "pc0_5", "pc1_0", "pc2_5", "pc5_0", "pc10"],
)
def test_measurement_nonnegative_fields_reject_negative_values(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError) as raised:
        MeasurementCreateRequest.model_validate(
            {"measured_at": NOW, field_name: -1}
        )

    assert raised.value.errors()[0]["loc"] == (field_name,)


@pytest.mark.parametrize("field_name", PARTICLE_COUNTER_FIELDS)
def test_particle_counter_accepts_postgres_integer_max(
    field_name: str,
) -> None:
    request = MeasurementCreateRequest.model_validate(
        {
            "measured_at": NOW,
            field_name: POSTGRES_INTEGER_MAX,
        }
    )

    assert getattr(request, field_name) == POSTGRES_INTEGER_MAX


@pytest.mark.parametrize("field_name", PARTICLE_COUNTER_FIELDS)
def test_particle_counter_rejects_value_above_postgres_integer_max(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError) as raised:
        MeasurementCreateRequest.model_validate(
            {
                "measured_at": NOW,
                field_name: POSTGRES_INTEGER_MAX + 1,
            }
        )

    assert raised.value.errors()[0]["loc"] == (field_name,)


@pytest.mark.parametrize("field_name", ["pm1", "pm25", "pm10"])
@pytest.mark.parametrize(
    "raw_value",
    ["1e999", "-1e999", "NaN", "Infinity", "-Infinity"],
)
def test_measurement_request_rejects_non_finite_pm_json(
    field_name: str,
    raw_value: str,
) -> None:
    payload = (
        '{"measured_at":"2026-07-23T08:30:00Z",'
        f'"{field_name}":{raw_value}}}'
    )

    with pytest.raises(ValidationError) as raised:
        MeasurementCreateRequest.model_validate_json(payload)

    assert raised.value.errors()[0]["loc"] == (field_name,)


@pytest.mark.parametrize("field_name", ["pm1", "pm25", "pm10"])
@pytest.mark.parametrize("value", [0.0, 1e308])
def test_measurement_request_accepts_finite_pm_values(
    field_name: str,
    value: float,
) -> None:
    request = MeasurementCreateRequest.model_validate(
        {"measured_at": NOW, field_name: value}
    )

    assert getattr(request, field_name) == value


@pytest.mark.parametrize(
    ("field_name", "valid_values", "invalid_values"),
    [
        ("temperature", (-40.0, 85.0), (-40.1, 85.1)),
        ("humidity", (0.0, 100.0), (-0.1, 100.1)),
    ],
)
def test_measurement_environmental_ranges_match_existing_orm_constraints(
    field_name: str,
    valid_values: tuple[float, float],
    invalid_values: tuple[float, float],
) -> None:
    for value in valid_values:
        assert (
            getattr(
                MeasurementCreateRequest.model_validate(
                    {"measured_at": NOW, field_name: value}
                ),
                field_name,
            )
            == value
        )

    for value in invalid_values:
        with pytest.raises(ValidationError):
            MeasurementCreateRequest.model_validate(
                {"measured_at": NOW, field_name: value}
            )


def test_device_response_reads_only_declared_scalar_attributes() -> None:
    device = Device(
        id=11,
        device_uid="monitor-11",
        name="Workshop",
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )

    response = DeviceResponse.model_validate(device)

    assert response.model_dump() == {
        "id": 11,
        "device_uid": "monitor-11",
        "name": "Workshop",
        "is_active": True,
        "created_at": NOW,
    }
    assert "runtime_state" not in DeviceResponse.model_fields


def test_transition_responses_do_not_access_expired_updated_at() -> None:
    class TransitionedDevice:
        id = 11
        device_uid = "monitor-11"
        name = "Workshop"
        is_active = False
        created_at = NOW

        @property
        def updated_at(self) -> datetime:
            raise AssertionError("expired updated_at was accessed")

    class TransitionedSession:
        id = 21
        device_id = 11
        status = "completed"
        started_at = NOW
        ended_at = NOW
        latitude = 51.1694
        longitude = 71.4491
        sample_count = 1
        created_at = NOW

        @property
        def updated_at(self) -> datetime:
            raise AssertionError("expired updated_at was accessed")

    device_response = DeviceResponse.model_validate(TransitionedDevice())
    session_response = SessionResponse.model_validate(
        TransitionedSession()
    )

    assert device_response.is_active is False
    assert session_response.status == "completed"


def test_session_response_exposes_operational_scalar_contract() -> None:
    session = MeasurementSession(
        id=21,
        device_id=11,
        status="active",
        started_at=NOW,
        ended_at=None,
        latitude=51.1694,
        longitude=71.4491,
        sample_count=0,
        created_at=NOW,
        updated_at=NOW,
    )

    response = SessionResponse.model_validate(session)

    assert response.model_dump() == {
        "id": 21,
        "device_id": 11,
        "status": "active",
        "started_at": NOW,
        "ended_at": None,
        "latitude": 51.1694,
        "longitude": 71.4491,
        "sample_count": 0,
        "created_at": NOW,
    }
    assert "raw_measurements" not in SessionResponse.model_fields
    assert "aqi_pm25" not in SessionResponse.model_fields


def test_measurement_response_has_stable_json_numeric_types() -> None:
    measurement = RawMeasurement(
        id=31,
        device_id=11,
        session_id=21,
        source_message_id="message-31",
        measured_at=NOW,
        received_at=NOW,
        temperature=21.5,
        humidity=44.25,
        pm1=3.0,
        pm25=7.5,
        pm10=12.0,
        pc0_3=100,
        pc0_5=90,
        pc1_0=80,
        pc2_5=70,
        pc5_0=60,
        pc10=50,
        latitude=51.1694,
        longitude=71.4491,
        is_valid=True,
        validation_note=None,
        created_at=NOW,
    )

    payload = MeasurementResponse.model_validate(
        measurement
    ).model_dump(mode="json")

    assert payload["pm25"] == 7.5
    assert isinstance(payload["pm25"], float)
    assert payload["pc0_3"] == 100
    assert isinstance(payload["pc0_3"], int)
    assert payload["latitude"] == 51.1694
    assert isinstance(payload["latitude"], float)


def test_telemetry_read_session_list_schema_has_exact_contract() -> None:
    response_schema = telemetry_schemas.SessionListResponse

    assert set(response_schema.model_fields) == {"items", "next_cursor"}
    assert response_schema.model_fields["items"].annotation == (
        list[SessionResponse]
    )
    assert response_schema.model_fields["next_cursor"].annotation == (
        str | None
    )
    assert response_schema.model_fields["items"].is_required()
    assert response_schema.model_fields["next_cursor"].is_required()
    assert set(SessionResponse.model_fields) == SESSION_RESPONSE_FIELDS
    assert FORBIDDEN_LIST_FIELDS.isdisjoint(response_schema.model_fields)


def test_telemetry_read_session_list_schema_serializes_orm_items() -> None:
    session = MeasurementSession(
        id=21,
        device_id=11,
        status="completed",
        started_at=NOW,
        ended_at=NOW,
        latitude=51.1694,
        longitude=71.4491,
        sample_count=17,
        created_at=NOW,
        updated_at=NOW,
    )

    response = telemetry_schemas.SessionListResponse.model_validate(
        {"items": [session], "next_cursor": "opaque-session-cursor"}
    )
    payload = response.model_dump(mode="json")

    assert set(payload) == {"items", "next_cursor"}
    assert set(payload["items"][0]) == SESSION_RESPONSE_FIELDS
    assert payload["items"][0]["started_at"] == (
        "2026-07-23T08:30:00Z"
    )
    assert payload["items"][0]["latitude"] == 51.1694
    assert isinstance(payload["items"][0]["latitude"], float)
    assert payload["items"][0]["sample_count"] == 17
    assert isinstance(payload["items"][0]["sample_count"], int)
    assert payload["next_cursor"] == "opaque-session-cursor"


def test_telemetry_read_session_list_schema_accepts_empty_page() -> None:
    response = telemetry_schemas.SessionListResponse(
        items=[],
        next_cursor=None,
    )

    assert response.model_dump(mode="json") == {
        "items": [],
        "next_cursor": None,
    }


def test_telemetry_read_measurement_list_schema_has_exact_contract() -> None:
    response_schema = telemetry_schemas.MeasurementListResponse

    assert set(response_schema.model_fields) == {"items", "next_cursor"}
    assert response_schema.model_fields["items"].annotation == (
        list[MeasurementResponse]
    )
    assert response_schema.model_fields["next_cursor"].annotation == (
        str | None
    )
    assert response_schema.model_fields["items"].is_required()
    assert response_schema.model_fields["next_cursor"].is_required()
    assert (
        set(MeasurementResponse.model_fields)
        == MEASUREMENT_RESPONSE_FIELDS
    )
    assert FORBIDDEN_LIST_FIELDS.isdisjoint(response_schema.model_fields)


def test_telemetry_read_measurement_list_schema_serializes_orm_items(
) -> None:
    measurement = RawMeasurement(
        id=31,
        device_id=11,
        session_id=21,
        source_message_id="message-31",
        measured_at=NOW,
        received_at=NOW,
        temperature=21.5,
        humidity=44.25,
        pm1=3.0,
        pm25=7.5,
        pm10=12.0,
        pc0_3=100,
        pc0_5=90,
        pc1_0=80,
        pc2_5=70,
        pc5_0=60,
        pc10=50,
        latitude=51.1694,
        longitude=71.4491,
        is_valid=True,
        validation_note=None,
        created_at=NOW,
    )

    response = telemetry_schemas.MeasurementListResponse.model_validate(
        {"items": [measurement], "next_cursor": "opaque-measurement-cursor"}
    )
    payload = response.model_dump(mode="json")

    assert set(payload) == {"items", "next_cursor"}
    assert set(payload["items"][0]) == MEASUREMENT_RESPONSE_FIELDS
    assert payload["items"][0]["measured_at"] == (
        "2026-07-23T08:30:00Z"
    )
    assert payload["items"][0]["pm25"] == 7.5
    assert isinstance(payload["items"][0]["pm25"], float)
    assert payload["items"][0]["pc0_3"] == 100
    assert isinstance(payload["items"][0]["pc0_3"], int)
    assert payload["next_cursor"] == "opaque-measurement-cursor"


def test_telemetry_read_measurement_list_schema_accepts_empty_page() -> None:
    response = telemetry_schemas.MeasurementListResponse(
        items=[],
        next_cursor=None,
    )

    assert response.model_dump(mode="json") == {
        "items": [],
        "next_cursor": None,
    }
