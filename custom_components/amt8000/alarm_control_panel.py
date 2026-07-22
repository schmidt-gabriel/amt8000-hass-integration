"""Defines the sensors for amt-8000."""
from datetime import timedelta
from threading import Lock
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity, AlarmControlPanelEntityFeature

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)


from .const import DOMAIN
from .coordinator import AmtCoordinator
from .isec2.client import Client as ISecClient


LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entries for amt-8000."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    isec_client = ISecClient(data["host"], data["port"])
    # A single lock is shared between the coordinator (polling) and the panel
    # entity (user commands). The AMT-8000 only accepts one session at a time,
    # so all access to it must be serialized once the blocking I/O runs in
    # executor threads instead of the (single-threaded) event loop.
    lock = Lock()
    coordinator = AmtCoordinator(hass, isec_client, data["password"], lock)
    LOGGER.info('setting up...')
    # coordinator.async_config_entry_first_refresh()
    sensors = [AmtAlarmPanel(coordinator, isec_client, data['password'], lock)]
    async_add_entities(sensors)


class AmtAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Define a Amt Alarm Panel."""

    _attr_supported_features = (
          AlarmControlPanelEntityFeature.ARM_AWAY
        # | AlarmControlPanelEntityFeature.ARM_NIGHT
        # | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(self, coordinator, isec_client: ISecClient, password, lock: Lock):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.status = None
        self.isec_client = isec_client
        self.password = password
        self._lock = lock
        self._is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the stored value on coordinator updates."""
        self.status = self.coordinator.data
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "AMT-8000"

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return "amt8000.control_panel"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.status is not None

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        if self.status is None:
            return "unknown"

        if self.status['siren'] == True:
            return "triggered"

        if(self.status["status"].startswith("armed_")):
          self._is_on = True

        return self.status["status"]

    def _run_command(self, command):
        """Run a blocking client command under the shared lock.

        connect/auth/<command>/close is executed atomically so that it never
        overlaps with the coordinator poll on the single-session panel.
        """
        with self._lock:
            self.isec_client.connect()
            try:
                self.isec_client.auth(self.password)
                return command()
            finally:
                self.isec_client.close()

    def _arm_away(self):
        """Arm AMT in away mode"""
        result = self._run_command(lambda: self.isec_client.arm_system(0))
        if result == "armed":
            return 'armed_away'

    def _disarm(self):
        """Disarm AMT"""
        result = self._run_command(lambda: self.isec_client.disarm_system(0))
        if result == "disarmed":
            return 'disarmed'

    def _trigger_alarm(self):
        """Trigger Alarm"""
        result = self._run_command(lambda: self.isec_client.panic(1))
        if result == "triggered":
            return "triggered"

    async def _async_run(self, func) -> None:
        """Run a blocking command off the event loop, then refresh state."""
        await self.hass.async_add_executor_job(func)
        await self.coordinator.async_request_refresh()

    def alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        self._disarm()

    async def async_alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        await self._async_run(self._disarm)

    def alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        self._arm_away()

    async def async_alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        await self._async_run(self._arm_away)

    def alarm_trigger(self, code=None) -> None:
        """Send alarm trigger command."""
        self._trigger_alarm()

    async def async_alarm_trigger(self, code=None) -> None:
        """Send alarm trigger command."""
        await self._async_run(self._trigger_alarm)

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._is_on

    def turn_on(self, **kwargs: Any) -> None:
        self._arm_away()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_run(self._arm_away)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._disarm()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_run(self._disarm)

