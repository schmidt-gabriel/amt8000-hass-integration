"""Data update coordinator for the AMT-8000 integration."""
import logging
from datetime import timedelta
from threading import Lock

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .isec2.client import Client as ISecClient

LOGGER = logging.getLogger(__name__)


class AmtCoordinator(DataUpdateCoordinator):
    """Coordinate the amt status update."""

    def __init__(self, hass, isec_client: ISecClient, password, lock: Lock):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="AMT-8000 Data Polling",
            update_interval=timedelta(seconds=10),
        )
        self.isec_client = isec_client
        self.password = password
        # Shared with the alarm panel entity so that polling and user commands
        # never touch the single-session panel from two executor threads at once.
        self._lock = lock

    def _fetch_status(self):
        """Connect, authenticate, read status (with per-zone data) and close.

        Runs in an executor thread; the lock serializes access to the panel.
        """
        with self._lock:
            self.isec_client.connect()
            try:
                self.isec_client.auth(self.password)
                return self.isec_client.status_with_zones()
            finally:
                self.isec_client.close()

    def read_zone_names(self):
        """Read the configured zone names once (blocking, under the lock)."""
        with self._lock:
            self.isec_client.connect()
            try:
                self.isec_client.auth(self.password)
                return self.isec_client.zone_names()
            finally:
                self.isec_client.close()

    async def _async_update_data(self):
        """Retrieve the current status without blocking the event loop."""
        try:
            return await self.hass.async_add_executor_job(self._fetch_status)
        except Exception as err:  # noqa: BLE001 - surfaced as UpdateFailed
            raise UpdateFailed(f"Error communicating with AMT-8000: {err}") from err

    def _run_locked(self, command):
        """Run a client command inside an authenticated, locked session.

        `command` receives the connected ISecClient and returns its result.
        Runs in an executor thread; the lock serializes access to the panel.
        """
        with self._lock:
            self.isec_client.connect()
            try:
                self.isec_client.auth(self.password)
                return command(self.isec_client)
            finally:
                self.isec_client.close()

    async def async_execute(self, command):
        """Run a command off the event loop, then refresh the status.

        Used by the alarm panel entity and the panic button so every write
        goes through the same lock as the polling loop.
        """
        result = await self.hass.async_add_executor_job(self._run_locked, command)
        await self.async_request_refresh()
        return result
