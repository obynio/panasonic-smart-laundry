"""Data update coordinator for Panasonic Smart Laundry."""

from __future__ import annotations

import logging
from datetime import timedelta

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
        self._was_running = False
        self._cycle_remaining_baseline: int | None = None

    async def _async_update_data(self) -> LaundryDeviceData:
        try:
            raw = await self.api.get_status(appliance_id=self.appliance_id)
        except PanasonicAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PanasonicApiError as err:
            logger.warning("Status update failed: %s", err)
            raw = {}

        data = build_device_data(raw)
        running = is_device_running(data)
        progress, baseline = compute_cycle_progress(
            data,
            running=running,
            was_running=self._was_running,
            baseline_minutes=self._cycle_remaining_baseline,
        )
        self._was_running = running
        self._cycle_remaining_baseline = baseline
        data.progress_percent = progress
        return data
