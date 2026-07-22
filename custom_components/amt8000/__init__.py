"""The AMT-8000 integration."""
from __future__ import annotations

import logging
from threading import Lock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AmtCoordinator
from .isec2.client import Client as ISecClient

LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AMT-8000 from a config entry."""
    isec_client = ISecClient(entry.data["host"], entry.data["port"])
    # One lock shared by the polling coordinator and every command entity:
    # the AMT-8000 only accepts a single session at a time.
    lock = Lock()
    coordinator = AmtCoordinator(hass, isec_client, entry.data["password"], lock)

    # First poll: raises ConfigEntryNotReady (and retries) if the panel is
    # unreachable, instead of setting up broken entities.
    await coordinator.async_config_entry_first_refresh()

    # Zone names are static config, read once here so entities can be named.
    try:
        zone_names = await hass.async_add_executor_job(coordinator.read_zone_names)
    except Exception as err:  # noqa: BLE001 - names are optional, keep setup alive
        LOGGER.warning("Could not read AMT-8000 zone names: %s", err)
        zone_names = {}

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": isec_client,
        "coordinator": coordinator,
        "lock": lock,
        "zone_names": zone_names,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Reload entities when the user changes options.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
