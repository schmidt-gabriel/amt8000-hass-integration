"""Diagnostic sensors for the AMT-8000: firmware, model and battery."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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
    """Set up the AMT-8000 diagnostic sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    entry_id = config_entry.entry_id
    async_add_entities(
        [
            AmtFirmwareSensor(coordinator, entry_id),
            AmtModelSensor(coordinator, entry_id),
            AmtBatterySensor(coordinator, entry_id),
        ]
    )


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
