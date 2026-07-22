"""Binary sensors for the AMT-8000: auto-detected zones, tamper, siren, battery."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AmtBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AMT-8000 binary sensors."""
    store = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = store["coordinator"]
    zone_names = store.get("zone_names", {})
    entry_id = config_entry.entry_id

    entities: list[BinarySensorEntity] = [
        AmtTamperSensor(coordinator, entry_id),
        AmtSirenSensor(coordinator, entry_id),
        AmtBatteryLowSensor(coordinator, entry_id),
    ]
    # Auto-detected zones: only those reported as configured by the panel.
    enabled = (coordinator.data or {}).get("enabledZones", [])
    entities += [
        AmtZoneSensor(coordinator, entry_id, zone, zone_names.get(zone))
        for zone in enabled
    ]
    async_add_entities(entities)


class AmtZoneSensor(AmtBaseEntity, BinarySensorEntity):
    """A configured alarm zone (on = open), with its name and signal level."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator, entry_id: str, zone: int, name: str | None) -> None:
        """Initialize the zone sensor."""
        super().__init__(coordinator, entry_id)
        self._zone = zone
        # Use the panel's zone name; fall back to "Zona N".
        self._attr_name = name or f"Zona {zone}"
        self._attr_unique_id = f"{entry_id}_zone_{zone}"

    @property
    def is_on(self) -> bool:
        """Return True if the zone is open."""
        return self._zone in self._data.get("openZones", [])

    @property
    def extra_state_attributes(self) -> dict:
        """Expose per-zone signal, alarm and bypass state."""
        data = self._data
        return {
            "zone": self._zone,
            "signal": data.get("zoneSignals", {}).get(self._zone),
            "firing": self._zone in data.get("firingZones", []),
            "bypassed": self._zone in data.get("bypassZones", []),
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
