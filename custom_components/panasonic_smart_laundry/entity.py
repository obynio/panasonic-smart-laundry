"""Shared Home Assistant entity helpers."""

from __future__ import annotations

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PanasonicSmartLaundryCoordinator


class PanasonicEntity(CoordinatorEntity[PanasonicSmartLaundryCoordinator]):
    """Base entity linked to the laundry device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PanasonicSmartLaundryCoordinator,
        entry_id: str,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        if description.translation_key is not None:
            self._attr_translation_key = description.translation_key
        else:
            self._attr_name = description.name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "manufacturer": "Panasonic",
            "model": coordinator.com_id,
            "name": coordinator.config_entry.title,
        }
        if description.icon:
            self._attr_icon = description.icon
