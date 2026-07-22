"""Panic button for the AMT-8000."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AmtBaseEntity

# Panic type sent to the panel (1 = audible panic).
PANIC_TYPE = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AMT-8000 panic button."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([AmtPanicButton(coordinator, config_entry.entry_id)])


class AmtPanicButton(AmtBaseEntity, ButtonEntity):
    """Button that triggers the panel's panic alarm."""

    _attr_name = "Pânico"
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the panic button."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_panic"

    async def async_press(self) -> None:
        """Trigger the panic alarm."""
        await self.coordinator.async_execute(
            lambda client: client.panic(PANIC_TYPE)
        )
