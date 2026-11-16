"""Diagnostics for the AMT-8000 integration.

"Download diagnostics" returns the latest polled status, including the raw
hex of the 0x0b4a (status) and 0x0b7a (extended status) payloads and a full
byte-indexed breakdown of both. Capture it while provoking a fault on the
panel to help map new offsets.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {"password", "host"}


def _jsonable(value: Any) -> Any:
    """Make the status dict JSON-safe (int dict keys -> str)."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _byte_breakdown(hex_payload: str | None) -> dict[str, str]:
    """Full per-byte dump {offset: "0xNN"} (0-based) of a hex payload."""
    if not hex_payload:
        return {}
    return {str(i): f"0x{b:02x}" for i, b in enumerate(bytes.fromhex(hex_payload))}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = store.get("coordinator")
    data = (coordinator.data if coordinator else None) or {}
    raw = data.get("raw") or {}
    status = {k: v for k, v in data.items() if k != "raw"}
    status_hex = raw.get("status")
    ext_hex = raw.get("extStatus")

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "last_update_success": (
            coordinator.last_update_success if coordinator else None
        ),
        "zone_names": _jsonable(getattr(coordinator, "zone_names", {}) or {}),
        "status": _jsonable(status),
        "raw": {
            "status_0b4a": status_hex,
            "status_0b4a_length": len(status_hex) // 2 if status_hex else 0,
            "ext_status_0b7a": ext_hex,
            "ext_status_0b7a_length": len(ext_hex) // 2 if ext_hex else 0,
            "status_0b4a_bytes": _byte_breakdown(status_hex),
            "ext_status_0b7a_bytes": _byte_breakdown(ext_hex),
        },
    }
