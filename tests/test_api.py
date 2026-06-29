"""Tests for Panasonic Smart Laundry API client behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from panasonic_smart_laundry.api import (
    PanasonicApiError,
    PanasonicSmartLaundryApi,
    _live_status_unavailable,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            'GET /laundry/v5/device/status/ failed with 400: {"code":"L2E05-017-1001"}',
            True,
        ),
        (
            'GET /laundry/v5/device/status/ failed with 400: {"code":"L2E05-017-0001"}',
            True,
        ),
        ("GET /laundry/v5/device/status/ failed with 500: server error", False),
    ],
)
def test_live_status_unavailable(message, expected):
    assert _live_status_unavailable(PanasonicApiError(message)) is expected


@pytest.mark.asyncio
async def test_get_status_uses_live_request_when_available():
    api = PanasonicSmartLaundryApi(AsyncMock(), "user", "pass", access_token="token")
    api._request = AsyncMock(  # noqa: SLF001
        return_value={"status": [{"id": "0121", "params": [{"value": "01"}]}]}
    )

    result = await api.get_status(appliance_id="appliance")

    assert result == {"0121": "01"}
    assert api._request.await_count == 1
    assert api._request.await_args.kwargs["extra_headers"] == {
        "X-ApplianceId": "appliance",
        "X-VerifyAppliance": "true",
        "X-Cached": "false",
    }


@pytest.mark.asyncio
async def test_get_status_falls_back_to_cached_on_live_unavailable():
    api = PanasonicSmartLaundryApi(AsyncMock(), "user", "pass", access_token="token")
    api._request = AsyncMock(  # noqa: SLF001
        side_effect=[
            PanasonicApiError(
                'GET /laundry/v5/device/status/ failed with 400: {"code":"L2E05-017-1001"}'
            ),
            {"status": [{"id": "0121", "params": [{"value": "00"}]}]},
        ]
    )

    result = await api.get_status(appliance_id="appliance")

    assert result == {"0121": "00"}
    assert api._request.await_count == 2
    assert api._request.await_args.kwargs["extra_headers"] == {
        "X-ApplianceId": "appliance",
        "X-VerifyAppliance": "true",
    }


@pytest.mark.asyncio
async def test_get_status_raises_when_live_and_cached_fail():
    api = PanasonicSmartLaundryApi(AsyncMock(), "user", "pass", access_token="token")
    api._request = AsyncMock(  # noqa: SLF001
        side_effect=PanasonicApiError("GET /laundry/v5/device/status/ failed with 503")
    )

    with pytest.raises(PanasonicApiError, match="503"):
        await api.get_status(appliance_id="appliance")

    assert api._request.await_count == 1
