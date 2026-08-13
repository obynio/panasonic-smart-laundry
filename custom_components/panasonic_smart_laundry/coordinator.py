"""Data update coordinator for Panasonic Smart Laundry."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import PanasonicApiError, PanasonicAuthError, PanasonicSmartLaundryApi
from .const import CONF_APPLIANCE_ID, CONF_COM_ID, DOMAIN, SCAN_INTERVAL
from .state import (
    LaundryDeviceData,
    build_device_data,
    compute_cycle_progress,
    cycle_should_reset,
    is_device_running,
)

logger = logging.getLogger(__name__)


class PanasonicSmartLaundryCoordinator(DataUpdateCoordinator[LaundryDeviceData]):
    """Poll Panasonic cloud status and expose normalized state."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: PanasonicSmartLaundryApi
    ) -> None:
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            config_entry=entry,
        )
        self.api = api
        self.com_id = entry.data[CONF_COM_ID]
        self.appliance_id = entry.data[CONF_APPLIANCE_ID]
        self._cycle_started_at: datetime | None = None

    async def _async_update_data(self) -> LaundryDeviceData:
        try:
            raw = await self.api.get_status(appliance_id=self.appliance_id)
        except PanasonicAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PanasonicApiError as err:
            logger.warning("Status update failed: %s", err)
            if self.data is not None:
                return self.data
            raw = {}

        if not raw and self.data is not None:
            return self.data

        data = build_device_data(raw)
        running = is_device_running(data)

        if not running:
            if cycle_should_reset(data):
                self._cycle_started_at = None
        elif self._cycle_started_at is None:
            self._cycle_started_at = datetime.now(timezone.utc)

        elapsed_minutes = None
        if running and self._cycle_started_at is not None:
            elapsed_minutes = (
                datetime.now(timezone.utc) - self._cycle_started_at
            ).total_seconds() / 60

        data.progress_percent = compute_cycle_progress(
            data,
            running=running,
            elapsed_minutes=elapsed_minutes,
        )
        return data
