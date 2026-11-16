"""Binary sensors for the AMT-8000: zones, tamper, siren, battery, problems."""
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
        AmtProblemSensor(coordinator, entry_id),
    ]
    # Auto-detected zones: only those reported as configured by the panel.
    data = coordinator.data or {}
    enabled = data.get("enabledZones", [])
    status_bytes = data.get("zoneStatusBytes", {})
    for zone in enabled:
        name = zone_names.get(zone)
        entities.append(
            AmtZoneSensor(
                coordinator, entry_id, zone, name,
                _zone_device_class(status_bytes.get(zone, 0x01)),
            )
        )
        entities.append(AmtZoneTamperSensor(coordinator, entry_id, zone, name))
        entities.append(AmtZoneBatterySensor(coordinator, entry_id, zone, name))
        entities.append(AmtZoneSupervisionSensor(coordinator, entry_id, zone, name))
    async_add_entities(entities)


def _zone_device_class(status_byte: int) -> BinarySensorDeviceClass:
    """Classify a zone from its 0x0b74 status byte.

    Bit 0 is the panel's interior/perimeter attribute: interior zones
    (motion/presence) have it set, perimeter zones (door/window) do not.
    """
    if status_byte & 0x01:
        return BinarySensorDeviceClass.MOTION
    return BinarySensorDeviceClass.DOOR


class AmtZoneSensor(AmtBaseEntity, BinarySensorEntity):
    """A configured alarm zone (on = open/triggered), with name and signal.

    The device class (motion vs door) is derived from the panel's own zone
    attribute, so presence zones get a motion-sensor icon and door/window
    zones get a door icon.
    """

    def __init__(
        self,
        coordinator,
        entry_id: str,
        zone: int,
        name: str | None,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialize the zone sensor."""
        super().__init__(coordinator, entry_id)
        self._zone = zone
        # Use the panel's zone name; fall back to "Zona N".
        self._attr_name = name or f"Zona {zone}"
        self._attr_unique_id = f"{entry_id}_zone_{zone}"
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool:
        """Return True if the zone is open."""
        return self._zone in self._data.get("openZones", [])

    @property
    def extra_state_attributes(self) -> dict:
        """Expose per-zone signal, alarm, bypass and tamper state."""
        data = self._data
        return {
            "zone": self._zone,
            "signal": data.get("zoneSignals", {}).get(self._zone),
            "firing": self._zone in data.get("firingZones", []),
            "bypassed": self._zone in data.get("bypassZones", []),
            "tamper": self._zone in data.get("tamperZones", []),
            "low_battery": self._zone in (data.get("lowBatteryZones") or []),
            "comm_failure": self._zone in (data.get("commFailureZones") or []),
        }


class AmtZoneTamperSensor(AmtBaseEntity, BinarySensorEntity):
    """Tamper detection for a single zone (on = tampered)."""

    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id: str, zone: int, name: str | None) -> None:
        """Initialize the per-zone tamper sensor."""
        super().__init__(coordinator, entry_id)
        self._zone = zone
        self._attr_name = f"Tamper {name or f'Zona {zone}'}"
        self._attr_unique_id = f"{entry_id}_zone_{zone}_tamper"

    @property
    def is_on(self) -> bool:
        """Return True if the zone is tampered."""
        return self._zone in self._data.get("tamperZones", [])


class AmtZoneBatterySensor(AmtBaseEntity, BinarySensorEntity):
    """Low battery for a single zone (on = low).

    Offset not yet verified live, so the entity starts disabled.
    """

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id: str, zone: int, name: str | None) -> None:
        """Initialize the per-zone battery sensor."""
        super().__init__(coordinator, entry_id)
        self._zone = zone
        self._attr_name = f"Bateria {name or f'Zona {zone}'}"
        self._attr_unique_id = f"{entry_id}_zone_{zone}_battery_low"

    @property
    def is_on(self) -> bool | None:
        """Return True if the zone battery is low (None if not reported)."""
        zones = self._data.get("lowBatteryZones")
        if zones is None:
            return None
        return self._zone in zones


class AmtZoneSupervisionSensor(AmtBaseEntity, BinarySensorEntity):
    """Supervision / communication failure for a single zone (on = failure).

    Offset not yet verified live, so the entity starts disabled.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id: str, zone: int, name: str | None) -> None:
        """Initialize the per-zone supervision sensor."""
        super().__init__(coordinator, entry_id)
        self._zone = zone
        self._attr_name = f"Supervisão {name or f'Zona {zone}'}"
        self._attr_unique_id = f"{entry_id}_zone_{zone}_comm_failure"

    @property
    def is_on(self) -> bool | None:
        """Return True if the zone lost communication (None if not reported)."""
        zones = self._data.get("commFailureZones")
        if zones is None:
            return None
        return self._zone in zones


class AmtProblemSensor(AmtBaseEntity, BinarySensorEntity):
    """Panel-level "problems detected" indicator.

    Only the panel's general problem flag (status byte 20 bit 0) and verified
    faults (zone tamper, panel tamper, panel battery low/dead) turn it on. The
    unverified per-zone battery/supervision bitmaps only label the cause in
    `active_problems`. Faults that cannot be decoded yet (e.g. a wireless
    siren supervision failure) show up as "Problema não identificado".
    """

    _attr_name = "Problema"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the problem sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_problem"

    def _zone_label(self, zone: int) -> str:
        # Same dict the zone entities were named from (updated in place).
        names = getattr(self.coordinator, "zone_names", None) or {}
        return names.get(zone) or f"Zona {zone}"

    def _verified_fault(self) -> bool:
        data = self._data
        return (
            bool(data.get("tamperZones"))
            or bool(data.get("tamper"))
            or data.get("batteryStatus") in ("low", "dead")
        )

    def _decoded_problems(self) -> list[str]:
        data = self._data
        enabled = set(data.get("enabledZones") or [])
        tamper_zones = data.get("tamperZones") or []
        problems = [
            f"Bateria fraca: {self._zone_label(z)}"
            for z in (data.get("lowBatteryZones") or [])
            if z in enabled
        ]
        problems += [
            f"Falha de supervisão: {self._zone_label(z)}"
            for z in (data.get("commFailureZones") or [])
            if z in enabled
        ]
        problems += [
            f"Violação (tamper): {self._zone_label(z)}" for z in tamper_zones
        ]
        if data.get("tamper") and not tamper_zones:
            problems.append("Violação (tamper) da central")
        if data.get("batteryStatus") in ("low", "dead"):
            problems.append("Bateria da central fraca")
        return problems

    @property
    def is_on(self) -> bool:
        """Return True on the panel's problem flag or a verified fault."""
        return bool(self._data.get("problem")) or self._verified_fault()

    @property
    def extra_state_attributes(self) -> dict:
        """List the active problems in Portuguese."""
        problems = self._decoded_problems()
        if not problems and self._data.get("problem"):
            problems = ["Problema não identificado"]
        return {"active_problems": problems}


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
