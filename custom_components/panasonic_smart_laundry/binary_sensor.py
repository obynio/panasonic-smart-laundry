"""Binary sensor platform for Panasonic Smart Laundry."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PanasonicEntity
from .coordinator import PanasonicSmartLaundryCoordinator
from .state import is_device_running


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic Smart Laundry binary sensors."""
    coordinator: PanasonicSmartLaundryCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RunningBinarySensor(coordinator, entry.entry_id)])


class RunningBinarySensor(PanasonicEntity, BinarySensorEntity):
    """Whether the machine is in an active cycle."""

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            entry_id,
            BinarySensorEntityDescription(
                key="running",
                translation_key="running",
                icon="mdi:washing-machine",
            ),
        )

    @property
    def is_on(self) -> bool | None:
        return is_device_running(self.coordinator.data)
