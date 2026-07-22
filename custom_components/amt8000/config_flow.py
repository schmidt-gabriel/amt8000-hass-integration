"""Config flow for AMT-8000 integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_MAX_ZONES,
    DEFAULT_MAX_ZONES,
    DOMAIN,
    MAX_ZONES,
    MIN_ZONES,
)
from .isec2.client import AuthError, Client as ISecClient

LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("port", default=9009): int,
        vol.Required("password"): str,
    }
)


def _validate_blocking(data: dict[str, Any]) -> None:
    """Connect and authenticate. Runs in an executor thread."""
    client = ISecClient(data["host"], data["port"])
    client.connect()
    try:
        client.auth(data["password"])
    finally:
        client.close()


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    await hass.async_add_executor_job(_validate_blocking, data)
    LOGGER.info("AMT logged in!")
    return {"title": "AMT-8000"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AMT-8000."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except (InvalidAuth, AuthError):
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Return the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle AMT-8000 options (number of zones to expose).

    `self.config_entry` is provided by the framework; do not assign it.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(CONF_MAX_ZONES, DEFAULT_MAX_ZONES)
        schema = vol.Schema(
            {
                vol.Required(CONF_MAX_ZONES, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_ZONES, max=MAX_ZONES)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
