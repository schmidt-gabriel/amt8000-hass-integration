"""The AMT-8000 integration."""
from __future__ import annotations

import logging
from threading import Lock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
    # unreachable, instead of setting up broken entities. Zone names are read
    # inside this same session and cached on the coordinator.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": isec_client,
        "coordinator": coordinator,
        "lock": lock,
        "zone_names": coordinator.zone_names,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Runs after the platforms so the panel entity is registered and linked to
    # its device, letting the migration complete on the first setup.
    _async_migrate_panel_area(hass)
    # Reload entities when the user changes options.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _async_migrate_panel_area(hass: HomeAssistant) -> None:
    """Move a legacy entity-level area from the panel entity to its device.

    The panel is the device's main entity (no name of its own), so HA flags it
    when it carries its own area. Installs upgraded from the pre-overhaul
    entity still have one; hand it to the device (if the device has none) and
    clear it from the entity. Idempotent: a no-op once the area is cleared.
    Must run after the platforms are set up, so the entity is device-linked.
    """
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        "alarm_control_panel", DOMAIN, "amt8000.control_panel"
    )
    if entity_id is None:
        return
    entity = ent_reg.async_get(entity_id)
    if entity is None or entity.area_id is None:
        return
    # Safety net: should not happen since this runs after the platforms link
    # the entity, but if it is not device-linked, keep the area untouched.
    if entity.device_id is None:
        return

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(entity.device_id)
    if device is None:
        return
    if device.area_id is None:
        dev_reg.async_update_device(device.id, area_id=entity.area_id)
        LOGGER.info(
            "Moved area %s from %s to its device %s",
            entity.area_id,
            entity_id,
            device.id,
        )
    else:
        LOGGER.info(
            "Cleared area %s from %s (device already has an area)",
            entity.area_id,
            entity_id,
        )
    ent_reg.async_update_entity(entity_id, area_id=None)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
