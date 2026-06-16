"""Sensor platform for Panasonic Smart Laundry."""

from __future__ import annotations

from collections.abc import Sequence

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PanasonicSmartLaundryCoordinator
from .entity import PanasonicEntity
from .labels import COURSE_PROPERTIES, get_course_label, get_display_label
from .state import parse_remaining_time

REMOTE_CONTROL_ICONS = {"01": "mdi:remote", "02": "mdi:remote-off"}

REMAINING_TIME_SENSORS: tuple[tuple[str, str, str], ...] = (
    ("00ED", "remaining_time", "mdi:timer-outline"),
    ("00DB", "wash_remaining_time", "mdi:timer-outline"),
    ("00DC", "dry_remaining_time", "mdi:tumble-dryer"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic Smart Laundry sensors."""
    coordinator: PanasonicSmartLaundryCoordinator = hass.data[DOMAIN][entry.entry_id]
    entry_id = entry.entry_id
    async_add_entities(
        [
            LabeledStateSensor(
                coordinator,
                entry_id,
                SensorEntityDescription(
                    key="0121",
                    translation_key="operation",
                    icon="mdi:washing-machine",
                ),
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
                    key="0100",
                    translation_key="remote_control",
                    icon="mdi:remote",
                ),
                icon_map=REMOTE_CONTROL_ICONS,
            ),
            LabeledStateSensor(
                coordinator,
                entry_id,
                SensorEntityDescription(
                    key="0136",
                    translation_key="detergent_supply",
                    icon="mdi:bucket-outline",
                ),
                icon_map={"01": "mdi:bucket-alert-outline"},
            ),
            LabeledStateSensor(
                coordinator,
                entry_id,
                SensorEntityDescription(
                    key="0137",
                    translation_key="softener_supply",
                    icon="mdi:scent",
                ),
                icon_map={"01": "mdi:scent-off"},
            ),
            *(
                RemainingTimeSensor(
                    coordinator,
                    entry_id,
                    prop_id=prop_id,
                    translation_key=translation_key,
                    icon=icon,
                )
                for prop_id, translation_key, icon in REMAINING_TIME_SENSORS
            ),
        ]
    )


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
            label = get_course_label(
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


class RemainingTimeSensor(PanasonicEntity, SensorEntity):
    """Remaining time sensor with a shared parser for total, wash, and dry."""

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
        data = self.coordinator.data
        if self._prop_id == "00ED":
            return data.remaining_minutes
        if self._prop_id == "00DB":
            return data.wash_remaining_minutes
        if self._prop_id == "00DC":
            return data.dry_remaining_minutes
        return parse_remaining_time(data.raw.get(self._prop_id))

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
