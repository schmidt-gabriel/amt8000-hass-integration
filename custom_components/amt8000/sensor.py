"""Sensors for the AMT-8000: firmware/model/battery and per-zone signal."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
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
    """Set up the AMT-8000 sensors."""
    store = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = store["coordinator"]
    zone_names = store.get("zone_names", {})
    entry_id = config_entry.entry_id

    entities: list[SensorEntity] = [
        AmtFirmwareSensor(coordinator, entry_id),
        AmtModelSensor(coordinator, entry_id),
        AmtBatterySensor(coordinator, entry_id),
    ]
    # One signal sensor per auto-detected zone.
    enabled = (coordinator.data or {}).get("enabledZones", [])
    entities += [
        AmtZoneSignalSensor(coordinator, entry_id, zone, zone_names.get(zone))
        for zone in enabled
    ]
    async_add_entities(entities)


class AmtFirmwareSensor(AmtBaseEntity, SensorEntity):
    """Panel firmware version."""

    _attr_name = "Firmware"
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the firmware sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_firmware"

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        return self._data.get("version")


class AmtModelSensor(AmtBaseEntity, SensorEntity):
    """Panel model."""

    _attr_name = "Modelo"
    _attr_icon = "mdi:shield-home"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the model sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_model"

    @property
    def native_value(self) -> str | None:
        """Return the model."""
        return self._data.get("model")


class AmtBatterySensor(AmtBaseEntity, SensorEntity):
    """Battery status (dead/low/middle/full)."""

    _attr_name = "Bateria"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["dead", "low", "middle", "full", "unknown"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_battery"

    @property
    def native_value(self) -> str | None:
        """Return the battery status."""
        return self._data.get("batteryStatus")


class AmtZoneSignalSensor(AmtBaseEntity, SensorEntity):
    """Wireless signal level of a zone (0 = worst, 10 = best)."""

    _attr_icon = "mdi:signal"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id: str, zone: int, name: str | None) -> None:
        """Initialize the zone signal sensor."""
        super().__init__(coordinator, entry_id)
        self._zone = zone
        self._attr_name = f"Sinal {name or f'Zona {zone}'}"
        self._attr_unique_id = f"{entry_id}_zone_{zone}_signal"

    @property
    def native_value(self) -> int | None:
        """Return the current signal level for the zone."""
        return self._data.get("zoneSignals", {}).get(self._zone)
