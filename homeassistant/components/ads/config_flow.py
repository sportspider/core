"""Config flow for ADS integration."""

from __future__ import annotations

import logging
from typing import Any

import pyads
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


def validate_net_id(net_id: str) -> bool:
    """Validate ADS Net ID format (x.x.x.x.x.x)."""
    parts = net_id.split(".")
    if len(parts) != 6:
        return False
    try:
        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return False
        return True
    except ValueError:
        return False


async def validate_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str] | None:
    """Validate the user input allows us to connect."""
    errors: dict[str, str] = {}

    net_id = data[CONF_DEVICE]
    port = data[CONF_PORT]
    ip_address = data.get(CONF_IP_ADDRESS)

    # Validate Net ID format
    if not validate_net_id(net_id):
        errors["base"] = "invalid_net_id"
        return errors

    # Try to connect to ADS device
    try:
        client = pyads.Connection(net_id, port, ip_address)
        await hass.async_add_executor_job(client.open)
        try:
            # Test connection by reading ADS state
            await hass.async_add_executor_job(client.read_state)
        finally:
            await hass.async_add_executor_job(client.close)
    except pyads.ADSError as err:
        _LOGGER.error("Failed to connect to ADS device: %s", err)
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error during connection test")
        errors["base"] = "unknown"

    return errors if errors else None


class AdsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ADS."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for duplicate entry
            self._async_abort_entries_match(
                {
                    CONF_DEVICE: user_input[CONF_DEVICE],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )

            # Validate connection
            validation_errors = await validate_connection(self.hass, user_input)
            if validation_errors:
                errors = validation_errors
            else:
                # Create entry
                title = f"ADS {user_input[CONF_DEVICE]}"
                if user_input.get(CONF_IP_ADDRESS):
                    title += f" ({user_input[CONF_IP_ADDRESS]})"

                return self.async_create_entry(
                    title=title,
                    data=user_input,
                )

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE): cv.string,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_IP_ADDRESS): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        # Check if already configured
        self._async_abort_entries_match(
            {
                CONF_DEVICE: import_data[CONF_DEVICE],
                CONF_PORT: import_data[CONF_PORT],
            }
        )

        # Validate connection
        validation_errors = await validate_connection(self.hass, import_data)
        if validation_errors:
            _LOGGER.error(
                "Failed to import ADS configuration from YAML: %s", validation_errors
            )
            return self.async_abort(reason="cannot_connect")

        # Create entry from YAML import
        title = f"ADS {import_data[CONF_DEVICE]}"
        if import_data.get(CONF_IP_ADDRESS):
            title += f" ({import_data[CONF_IP_ADDRESS]})"

        return self.async_create_entry(
            title=title,
            data=import_data,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry

        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate connection
            validation_errors = await validate_connection(self.hass, user_input)
            if validation_errors:
                errors = validation_errors
            else:
                # Update entry
                title = f"ADS {user_input[CONF_DEVICE]}"
                if user_input.get(CONF_IP_ADDRESS):
                    title += f" ({user_input[CONF_IP_ADDRESS]})"

                return self.async_update_reload_and_abort(
                    entry,
                    title=title,
                    data=user_input,
                )

        # Show form with current values
        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default=entry.data[CONF_DEVICE]): cv.string,
                vol.Required(CONF_PORT, default=entry.data[CONF_PORT]): cv.port,
                vol.Optional(
                    CONF_IP_ADDRESS, default=entry.data.get(CONF_IP_ADDRESS)
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AdsOptionsFlowHandler:
        """Get the options flow for this handler."""
        return AdsOptionsFlowHandler()


class AdsOptionsFlowHandler(OptionsFlow):
    """Handle ADS options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the ADS options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        # Currently no options to configure, just show empty form
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
