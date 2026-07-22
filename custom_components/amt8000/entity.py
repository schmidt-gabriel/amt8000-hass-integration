"""Base entity for the AMT-8000 integration."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AmtCoordinator


class AmtBaseEntity(CoordinatorEntity[AmtCoordinator]):
    """Common base: groups every entity under one AMT-8000 device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AmtCoordinator, entry_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id

    @property
    def _data(self) -> dict:
        """Return the latest status dict (or an empty dict)."""
        return self.coordinator.data or {}

    @property
    def available(self) -> bool:
        """Entity is available while the coordinator has data."""
        return super().available and self.coordinator.data is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Group all entities under a single device."""
        data = self._data
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name="AMT-8000",
            manufacturer=MANUFACTURER,
            model=data.get("model", "AMT-8000"),
            sw_version=data.get("version"),
        )
