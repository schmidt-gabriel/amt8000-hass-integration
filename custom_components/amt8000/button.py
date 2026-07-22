"""Panic button for the AMT-8000."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

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


class AmtPanicButton(ButtonEntity):
    """Button that triggers the panel's panic alarm.

    Intentionally NOT a CoordinatorEntity: a button is a stateless trigger.
    Subscribing to coordinator updates makes the entity emit state_changed
    events whenever polling availability flaps (the AMT-8000 is single-session,
    so polls occasionally fail), and Home Assistant's logbook labels *any*
    button state change as "Pressed" - producing spurious press entries on
    restart. Keeping it a plain button leaves it in "unknown" until an actual
    press, so no false events are logged.
    """

    _attr_has_entity_name = True
    _attr_name = "Pânico"
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the panic button."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_panic"
        # Attach to the same device as the other entities via matching identifiers.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)})

    async def async_press(self) -> None:
        """Trigger the panic alarm."""
        await self._coordinator.async_execute(
            lambda client: client.panic(PANIC_TYPE)
        )
