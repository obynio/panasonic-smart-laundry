"""Shared Home Assistant entity helpers."""

from __future__ import annotations

import inspect

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PanasonicSmartLaundryCoordinator

ENTITY_DISPLAY_ORDER: dict[str, int] = {
    "course": 0,
    "transition": 1,
    "operation": 2,
    "remote_control": 3,
    "detergent_supply": 4,
    "softener_supply": 5,
    "remaining_time": 6,
    "wash_remaining_time": 7,
    "dry_remaining_time": 8,
    "running": 9,
}


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

    async def async_added_to_hass(self) -> None:
        """Set entity registry display order when supported."""
        await super().async_added_to_hass()
        translation_key = self.translation_key
        if translation_key is None:
            return
        order = ENTITY_DISPLAY_ORDER.get(translation_key)
        if order is None:
            return
        registry = er.async_get(self.hass)
        if registry.async_get(self.entity_id) is None:
            return
        if "order" not in inspect.signature(registry.async_update_entity).parameters:
            return
        registry.async_update_entity(self.entity_id, order=order)
