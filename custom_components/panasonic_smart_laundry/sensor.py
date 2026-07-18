"""Sensor platform for Panasonic Smart Laundry."""

from __future__ import annotations

from collections.abc import Sequence

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PanasonicSmartLaundryCoordinator
from .entity import PanasonicEntity
from .labels import (
    COURSE_PROPERTIES,
    get_display_label,
    has_bundled_property,
    resolve_course_label,
)

REMOTE_CONTROL_ICONS = {"01": "mdi:remote", "02": "mdi:remote-off"}
DOOR_ICONS = {"41": "mdi:door-open", "42": "mdi:door-closed"}
DOOR_PROPERTY = "00B0"

SUPPLY_SENSORS: tuple[tuple[str, str, str, dict[str, str]], ...] = (
    ("0136", "detergent_supply", "mdi:bucket-outline", {"01": "mdi:bucket-alert-outline"}),
    ("0137", "softener_supply", "mdi:scent", {"01": "mdi:scent-off"}),
)


def _machine_supports_supply(
    coordinator: PanasonicSmartLaundryCoordinator, prop_id: str
) -> bool:
    api = coordinator.api
    if api.supports_supply_property(prop_id):
        return True
    return has_bundled_property(coordinator.com_id, prop_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic Smart Laundry sensors."""
    coordinator: PanasonicSmartLaundryCoordinator = hass.data[DOMAIN][entry.entry_id]
    entry_id = entry.entry_id
    entities: list[SensorEntity] = [
        LabeledStateSensor(
            coordinator,
            entry_id,
            SensorEntityDescription(
                key="00D0",
                translation_key="course",
                icon="mdi:tune-variant",
            ),
            alternate_props=COURSE_PROPERTIES[1:],
        ),
        LabeledStateSensor(
            coordinator,
            entry_id,
            SensorEntityDescription(
                key="00E2",
                translation_key="transition",
                icon="mdi:state-machine",
            ),
            default_value="00",
        ),
        LabeledStateSensor(
            coordinator,
            entry_id,
            SensorEntityDescription(
                key="0121",
                translation_key="operation",
                icon="mdi:washing-machine",
            ),
        ),
    ]
    for prop_id, translation_key, icon, icon_map in SUPPLY_SENSORS:
        if not _machine_supports_supply(coordinator, prop_id):
            continue
        entities.append(
            LabeledStateSensor(
                coordinator,
                entry_id,
                SensorEntityDescription(
                    key=prop_id,
                    translation_key=translation_key,
                    icon=icon,
                ),
                icon_map=icon_map,
            )
        )
    entities.append(CourseProgressSensor(coordinator, entry_id))
    entities.append(
        RemainingTimeSensor(
            coordinator,
            entry_id,
            prop_id="00ED",
            translation_key="remaining_time",
            icon="mdi:timer-outline",
        )
    )
    if has_bundled_property(coordinator.com_id, DOOR_PROPERTY):
        entities.append(
            LabeledStateSensor(
                coordinator,
                entry_id,
                SensorEntityDescription(
                    key=DOOR_PROPERTY,
                    translation_key="door",
                    icon="mdi:door",
                ),
                icon_map=DOOR_ICONS,
            )
        )
    entities.append(
        LabeledStateSensor(
            coordinator,
            entry_id,
            SensorEntityDescription(
                key="0100",
                translation_key="remote_control",
                icon="mdi:remote",
            ),
            icon_map=REMOTE_CONTROL_ICONS,
        )
    )
    async_add_entities(entities)


class LabeledStateSensor(PanasonicEntity, SensorEntity):
    """Sensor that shows a translated label and keeps the raw code in attributes."""

    def __init__(
        self,
        coordinator: PanasonicSmartLaundryCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
        *,
        alternate_props: Sequence[str] = (),
        icon_map: dict[str, str] | None = None,
        default_value: str | None = None,
    ) -> None:
        super().__init__(coordinator, entry_id, description)
        self._prop_ids = (description.key, *alternate_props)
        self._is_course = bool(alternate_props)
        self._icon_map = icon_map or {}
        self._default_value = default_value

    def _resolved_value(self) -> tuple[str | None, str | None]:
        raw = self.coordinator.data.raw
        for index, prop_id in enumerate(self._prop_ids):
            value = raw.get(prop_id)
            if value not in (None, ""):
                return prop_id, value
            if index == 0 and self._default_value is not None:
                return prop_id, self._default_value
        return None, None

    @property
    def native_value(self) -> str | None:
        prop_id, value = self._resolved_value()
        if prop_id is None or value is None:
            return None

        japanese = self.hass.config.language.startswith("ja")
        if self._is_course:
            label = resolve_course_label(
                self.coordinator.api,
                self.coordinator.com_id,
                self.coordinator.data.raw,
                japanese=japanese,
            )
        else:
            label = get_display_label(
                self.coordinator.api,
                self.coordinator.com_id,
                prop_id,
                value,
                japanese=japanese,
            )
        return label or value

    @property
    def icon(self) -> str | None:
        _, value = self._resolved_value()
        if value and value in self._icon_map:
            return self._icon_map[value]
        return self._attr_icon

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        prop_id, value = self._resolved_value()
        return {"raw_value": value, "property": prop_id}


class CourseProgressSensor(PanasonicEntity, SensorEntity):
    """Estimated whole-course progress from total remaining time."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: PanasonicSmartLaundryCoordinator,
        entry_id: str,
    ) -> None:
        super().__init__(
            coordinator,
            entry_id,
            SensorEntityDescription(
                key="progress",
                translation_key="progress",
                icon="mdi:progress-clock",
            ),
        )

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.progress_percent


class RemainingTimeSensor(PanasonicEntity, SensorEntity):
    """Total remaining time sensor."""

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: PanasonicSmartLaundryCoordinator,
        entry_id: str,
        *,
        prop_id: str,
        translation_key: str,
        icon: str,
    ) -> None:
        super().__init__(
            coordinator,
            entry_id,
            SensorEntityDescription(
                key=prop_id,
                translation_key=translation_key,
                icon=icon,
            ),
        )
        self._prop_id = prop_id

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.remaining_minutes

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        raw_value = self.coordinator.data.raw.get(self._prop_id)
        parsed = self.native_value
        if parsed is None:
            return {"raw_value": raw_value, "hours": None, "minutes": None}
        return {
            "raw_value": raw_value,
            "hours": parsed // 60,
            "minutes": parsed % 60,
        }
