"""Alarm control panel for the AMT-8000."""
from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AmtBaseEntity

LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Map the panel's status string to a Home Assistant alarm state.
_STATE_MAP = {
    "disarmed": "disarmed",
    "armed_away": "armed_away",
    "partial_armed": "armed_home",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AMT-8000 alarm panel."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([AmtAlarmPanel(coordinator, config_entry.entry_id)])


class AmtAlarmPanel(AmtBaseEntity, AlarmControlPanelEntity):
    """AMT-8000 alarm control panel."""

    _attr_name = None
    _attr_code_arm_required = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the panel, keeping the original unique_id."""
        super().__init__(coordinator, entry_id)
        # Preserve the historical unique_id so the existing entity/history is kept.
        self._attr_unique_id = "amt8000.control_panel"

    @property
    def state(self) -> str | None:
        """Return the alarm state."""
        data = self._data
        if not data:
            return None
        if data.get("siren"):
            return "triggered"
        return _STATE_MAP.get(data.get("status"))

    async def async_alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        await self.coordinator.async_execute(lambda client: client.disarm_system(0))

    async def async_alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        await self.coordinator.async_execute(lambda client: client.arm_system(0))

    async def async_alarm_trigger(self, code=None) -> None:
        """Trigger the panic alarm."""
        await self.coordinator.async_execute(lambda client: client.panic(1))
