"""Binary sensors for the AMT-8000: zones, tamper, siren and low battery."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MAX_ZONES, DEFAULT_MAX_ZONES, DOMAIN
from .entity import AmtBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AMT-8000 binary sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    entry_id = config_entry.entry_id
    max_zones = config_entry.options.get(CONF_MAX_ZONES, DEFAULT_MAX_ZONES)

    entities: list[BinarySensorEntity] = [
        AmtTamperSensor(coordinator, entry_id),
        AmtSirenSensor(coordinator, entry_id),
        AmtBatteryLowSensor(coordinator, entry_id),
    ]
    entities += [
        AmtZoneSensor(coordinator, entry_id, zone)
        for zone in range(1, max_zones + 1)
    ]
    async_add_entities(entities)


class AmtZoneSensor(AmtBaseEntity, BinarySensorEntity):
    """A single alarm zone (on = open)."""

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator, entry_id: str, zone: int) -> None:
        """Initialize the zone sensor."""
        super().__init__(coordinator, entry_id)
        self._zone = zone
        self._attr_name = f"Zona {zone}"
        self._attr_unique_id = f"{entry_id}_zone_{zone}"

    @property
    def is_on(self) -> bool:
        """Return True if the zone is open."""
        return self._zone in self._data.get("openZones", [])

    @property
    def extra_state_attributes(self) -> dict:
        """Expose per-zone alarm/bypass state as attributes."""
        return {
            "firing": self._zone in self._data.get("firingZones", []),
            "bypassed": self._zone in self._data.get("bypassZones", []),
        }


class AmtTamperSensor(AmtBaseEntity, BinarySensorEntity):
    """Panel tamper detection."""

    _attr_name = "Violação (tamper)"
    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the tamper sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_tamper"

    @property
    def is_on(self) -> bool:
        """Return True if tamper is active."""
        return bool(self._data.get("tamper"))


class AmtSirenSensor(AmtBaseEntity, BinarySensorEntity):
    """Siren active indicator."""

    _attr_name = "Sirene"
    _attr_device_class = BinarySensorDeviceClass.SOUND

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the siren sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_siren"

    @property
    def is_on(self) -> bool:
        """Return True if the siren is sounding."""
        return bool(self._data.get("siren"))


class AmtBatteryLowSensor(AmtBaseEntity, BinarySensorEntity):
    """Low battery indicator."""

    _attr_name = "Bateria baixa"
    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the low battery sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_battery_low"

    @property
    def is_on(self) -> bool:
        """Return True if the battery is low or dead."""
        return self._data.get("batteryStatus") in ("low", "dead")
