"""Read-only query-service contracts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ActiveSessionNotFoundError,
    DeviceNotFoundError,
)
from app.db.models import Device, MeasurementSession
from app.services.queries import (
    ActiveSessionQueryService,
    DeviceQueryService,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _session() -> Mock:
    return Mock(spec=AsyncSession)


def _assert_read_only(session: Mock) -> None:
    for method_name in ("begin", "commit", "rollback", "flush"):
        getattr(session, method_name).assert_not_called()


@pytest.mark.anyio
async def test_device_query_returns_repository_result_without_writes() -> None:
    session = _session()
    expected = Device(id=7, device_uid="monitor-7")
    service = DeviceQueryService(session)
    service.device_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=expected)
    )

    actual = await service.get_device(device_id=7)

    assert actual is expected
    service.device_repository.get_by_id.assert_awaited_once_with(7)
    _assert_read_only(session)


@pytest.mark.anyio
async def test_device_query_raises_explicit_missing_error() -> None:
    session = _session()
    service = DeviceQueryService(session)
    service.device_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None)
    )

    with pytest.raises(DeviceNotFoundError):
        await service.get_device(device_id=7)

    _assert_read_only(session)


@pytest.mark.anyio
async def test_active_session_query_returns_unlocked_repository_result() -> None:
    session = _session()
    expected = MeasurementSession(id=8, device_id=7, status="active")
    service = ActiveSessionQueryService(session)
    service.session_repository = SimpleNamespace(
        get_active_for_device=AsyncMock(return_value=expected)
    )

    actual = await service.get_active_session(device_id=7)

    assert actual is expected
    service.session_repository.get_active_for_device.assert_awaited_once_with(7)
    _assert_read_only(session)


@pytest.mark.anyio
async def test_active_session_query_raises_explicit_missing_error() -> None:
    session = _session()
    service = ActiveSessionQueryService(session)
    service.session_repository = SimpleNamespace(
        get_active_for_device=AsyncMock(return_value=None)
    )

    with pytest.raises(ActiveSessionNotFoundError):
        await service.get_active_session(device_id=7)

    _assert_read_only(session)
