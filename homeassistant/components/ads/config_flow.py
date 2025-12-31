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
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

from .const import CONF_ADS_VAR, DEFAULT_PORT, DOMAIN, AdsType

_LOGGER = logging.getLogger(__name__)

# Config entry option keys
CONF_ENTITIES = "entities"
CONF_ENTITY_ID = "entity_id"
CONF_ADS_TYPE = "adstype"
CONF_ADS_VAR_BRIGHTNESS = "adsvar_brightness"
CONF_ADS_VAR_POSITION = "adsvar_position"
CONF_ADS_VAR_SET_POSITION = "adsvar_set_position"
CONF_ADS_VAR_OPEN = "adsvar_open"
CONF_ADS_VAR_CLOSE = "adsvar_close"
CONF_ADS_VAR_STOP = "adsvar_stop"
CONF_ADS_FACTOR = "factor"
CONF_STATE_CLASS = "state_class"

# Entity types
ENTITY_TYPE_SWITCH = "switch"
ENTITY_TYPE_LIGHT = "light"
ENTITY_TYPE_SENSOR = "sensor"
ENTITY_TYPE_BINARY_SENSOR = "binary_sensor"
ENTITY_TYPE_COVER = "cover"

ENTITY_TYPES = [
    ENTITY_TYPE_SWITCH,
    ENTITY_TYPE_LIGHT,
    ENTITY_TYPE_SENSOR,
    ENTITY_TYPE_BINARY_SENSOR,
    ENTITY_TYPE_COVER,
]


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

    def __init__(self) -> None:
        """Initialize options flow."""
        self._entities: list[dict[str, Any]] = []
        self._entity_to_edit: dict[str, Any] | None = None
        self._entity_index: int | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the ADS options - main menu."""
        # Load existing entities from options
        self._entities = list(self.config_entry.options.get(CONF_ENTITIES, []))

        return self.async_show_menu(
            step_id="init",
            menu_options=["add_entity", "edit_entity", "remove_entity", "finish"],
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish options flow."""
        return self.async_create_entry(data={CONF_ENTITIES: self._entities})

    async def async_step_add_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entity_type = user_input[CONF_TYPE]
            # Store entity type and move to specific configuration
            self._entity_to_edit = {CONF_TYPE: entity_type}
            
            # Route to appropriate configuration step
            if entity_type == ENTITY_TYPE_SWITCH:
                return await self.async_step_configure_switch()
            if entity_type == ENTITY_TYPE_LIGHT:
                return await self.async_step_configure_light()
            if entity_type == ENTITY_TYPE_SENSOR:
                return await self.async_step_configure_sensor()
            if entity_type == ENTITY_TYPE_BINARY_SENSOR:
                return await self.async_step_configure_binary_sensor()
            if entity_type == ENTITY_TYPE_COVER:
                return await self.async_step_configure_cover()

        # Show entity type selection
        data_schema = vol.Schema(
            {
                vol.Required(CONF_TYPE): vol.In(
                    {
                        ENTITY_TYPE_SWITCH: "Switch",
                        ENTITY_TYPE_LIGHT: "Light",
                        ENTITY_TYPE_SENSOR: "Sensor",
                        ENTITY_TYPE_BINARY_SENSOR: "Binary Sensor",
                        ENTITY_TYPE_COVER: "Cover",
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="add_entity",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_configure_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a switch entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate unique entity name
            entity_id = user_input[CONF_NAME].lower().replace(" ", "_")
            if self._entity_index is None and any(
                e.get(CONF_ENTITY_ID) == entity_id for e in self._entities
            ):
                errors[CONF_NAME] = "entity_exists"
            else:
                # Build entity configuration
                entity_config = {
                    CONF_TYPE: ENTITY_TYPE_SWITCH,
                    CONF_ENTITY_ID: entity_id,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_ADS_VAR: user_input[CONF_ADS_VAR],
                }
                
                if self._entity_index is not None:
                    # Edit existing entity
                    self._entities[self._entity_index] = entity_config
                else:
                    # Add new entity
                    self._entities.append(entity_config)
                
                # Reset state and go back to menu
                self._entity_to_edit = None
                self._entity_index = None
                return await self.async_step_init()

        # Get defaults for edit mode
        defaults = {}
        if self._entity_to_edit and self._entity_index is not None:
            defaults = {
                CONF_NAME: self._entity_to_edit.get(CONF_NAME, ""),
                CONF_ADS_VAR: self._entity_to_edit.get(CONF_ADS_VAR, ""),
            }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): cv.string,
                vol.Required(
                    CONF_ADS_VAR, default=defaults.get(CONF_ADS_VAR, "")
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="configure_switch",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_configure_light(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a light entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate unique entity name
            entity_id = user_input[CONF_NAME].lower().replace(" ", "_")
            if self._entity_index is None and any(
                e.get(CONF_ENTITY_ID) == entity_id for e in self._entities
            ):
                errors[CONF_NAME] = "entity_exists"
            else:
                # Build entity configuration
                entity_config = {
                    CONF_TYPE: ENTITY_TYPE_LIGHT,
                    CONF_ENTITY_ID: entity_id,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_ADS_VAR: user_input[CONF_ADS_VAR],
                }
                
                # Add optional brightness variable
                if user_input.get(CONF_ADS_VAR_BRIGHTNESS):
                    entity_config[CONF_ADS_VAR_BRIGHTNESS] = user_input[
                        CONF_ADS_VAR_BRIGHTNESS
                    ]
                
                if self._entity_index is not None:
                    # Edit existing entity
                    self._entities[self._entity_index] = entity_config
                else:
                    # Add new entity
                    self._entities.append(entity_config)
                
                # Reset state and go back to menu
                self._entity_to_edit = None
                self._entity_index = None
                return await self.async_step_init()

        # Get defaults for edit mode
        defaults = {}
        if self._entity_to_edit and self._entity_index is not None:
            defaults = {
                CONF_NAME: self._entity_to_edit.get(CONF_NAME, ""),
                CONF_ADS_VAR: self._entity_to_edit.get(CONF_ADS_VAR, ""),
                CONF_ADS_VAR_BRIGHTNESS: self._entity_to_edit.get(
                    CONF_ADS_VAR_BRIGHTNESS, ""
                ),
            }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): cv.string,
                vol.Required(
                    CONF_ADS_VAR, default=defaults.get(CONF_ADS_VAR, "")
                ): cv.string,
                vol.Optional(
                    CONF_ADS_VAR_BRIGHTNESS,
                    default=defaults.get(CONF_ADS_VAR_BRIGHTNESS, ""),
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="configure_light",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_configure_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a sensor entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate unique entity name
            entity_id = user_input[CONF_NAME].lower().replace(" ", "_")
            if self._entity_index is None and any(
                e.get(CONF_ENTITY_ID) == entity_id for e in self._entities
            ):
                errors[CONF_NAME] = "entity_exists"
            else:
                # Build entity configuration
                entity_config = {
                    CONF_TYPE: ENTITY_TYPE_SENSOR,
                    CONF_ENTITY_ID: entity_id,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_ADS_VAR: user_input[CONF_ADS_VAR],
                    CONF_ADS_TYPE: user_input[CONF_ADS_TYPE],
                }
                
                # Add optional fields
                if user_input.get(CONF_UNIT_OF_MEASUREMENT):
                    entity_config[CONF_UNIT_OF_MEASUREMENT] = user_input[
                        CONF_UNIT_OF_MEASUREMENT
                    ]
                if user_input.get(CONF_DEVICE_CLASS):
                    entity_config[CONF_DEVICE_CLASS] = user_input[CONF_DEVICE_CLASS]
                if user_input.get(CONF_STATE_CLASS):
                    entity_config[CONF_STATE_CLASS] = user_input[CONF_STATE_CLASS]
                if user_input.get(CONF_ADS_FACTOR):
                    entity_config[CONF_ADS_FACTOR] = user_input[CONF_ADS_FACTOR]
                
                if self._entity_index is not None:
                    # Edit existing entity
                    self._entities[self._entity_index] = entity_config
                else:
                    # Add new entity
                    self._entities.append(entity_config)
                
                # Reset state and go back to menu
                self._entity_to_edit = None
                self._entity_index = None
                return await self.async_step_init()

        # Get defaults for edit mode
        defaults = {}
        if self._entity_to_edit and self._entity_index is not None:
            defaults = {
                CONF_NAME: self._entity_to_edit.get(CONF_NAME, ""),
                CONF_ADS_VAR: self._entity_to_edit.get(CONF_ADS_VAR, ""),
                CONF_ADS_TYPE: self._entity_to_edit.get(CONF_ADS_TYPE, AdsType.INT),
                CONF_UNIT_OF_MEASUREMENT: self._entity_to_edit.get(
                    CONF_UNIT_OF_MEASUREMENT, ""
                ),
                CONF_DEVICE_CLASS: self._entity_to_edit.get(CONF_DEVICE_CLASS, ""),
                CONF_STATE_CLASS: self._entity_to_edit.get(CONF_STATE_CLASS, ""),
                CONF_ADS_FACTOR: self._entity_to_edit.get(CONF_ADS_FACTOR, ""),
            }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): cv.string,
                vol.Required(
                    CONF_ADS_VAR, default=defaults.get(CONF_ADS_VAR, "")
                ): cv.string,
                vol.Required(
                    CONF_ADS_TYPE, default=defaults.get(CONF_ADS_TYPE, AdsType.INT)
                ): vol.In(
                    {
                        AdsType.BOOL: "Boolean",
                        AdsType.BYTE: "Byte",
                        AdsType.INT: "Integer (16-bit)",
                        AdsType.UINT: "Unsigned Integer (16-bit)",
                        AdsType.SINT: "Short Integer (8-bit)",
                        AdsType.USINT: "Unsigned Short Integer (8-bit)",
                        AdsType.DINT: "Double Integer (32-bit)",
                        AdsType.UDINT: "Unsigned Double Integer (32-bit)",
                        AdsType.WORD: "Word (16-bit)",
                        AdsType.DWORD: "Double Word (32-bit)",
                        AdsType.REAL: "Real (32-bit float)",
                        AdsType.LREAL: "Long Real (64-bit float)",
                    }
                ),
                vol.Optional(
                    CONF_UNIT_OF_MEASUREMENT,
                    default=defaults.get(CONF_UNIT_OF_MEASUREMENT, ""),
                ): cv.string,
                vol.Optional(
                    CONF_DEVICE_CLASS, default=defaults.get(CONF_DEVICE_CLASS, "")
                ): cv.string,
                vol.Optional(
                    CONF_STATE_CLASS, default=defaults.get(CONF_STATE_CLASS, "")
                ): cv.string,
                vol.Optional(
                    CONF_ADS_FACTOR, default=defaults.get(CONF_ADS_FACTOR, "")
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="configure_sensor",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_configure_binary_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a binary sensor entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate unique entity name
            entity_id = user_input[CONF_NAME].lower().replace(" ", "_")
            if self._entity_index is None and any(
                e.get(CONF_ENTITY_ID) == entity_id for e in self._entities
            ):
                errors[CONF_NAME] = "entity_exists"
            else:
                # Build entity configuration
                entity_config = {
                    CONF_TYPE: ENTITY_TYPE_BINARY_SENSOR,
                    CONF_ENTITY_ID: entity_id,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_ADS_VAR: user_input[CONF_ADS_VAR],
                }
                
                # Add optional device class
                if user_input.get(CONF_DEVICE_CLASS):
                    entity_config[CONF_DEVICE_CLASS] = user_input[CONF_DEVICE_CLASS]
                
                if self._entity_index is not None:
                    # Edit existing entity
                    self._entities[self._entity_index] = entity_config
                else:
                    # Add new entity
                    self._entities.append(entity_config)
                
                # Reset state and go back to menu
                self._entity_to_edit = None
                self._entity_index = None
                return await self.async_step_init()

        # Get defaults for edit mode
        defaults = {}
        if self._entity_to_edit and self._entity_index is not None:
            defaults = {
                CONF_NAME: self._entity_to_edit.get(CONF_NAME, ""),
                CONF_ADS_VAR: self._entity_to_edit.get(CONF_ADS_VAR, ""),
                CONF_DEVICE_CLASS: self._entity_to_edit.get(CONF_DEVICE_CLASS, ""),
            }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): cv.string,
                vol.Required(
                    CONF_ADS_VAR, default=defaults.get(CONF_ADS_VAR, "")
                ): cv.string,
                vol.Optional(
                    CONF_DEVICE_CLASS, default=defaults.get(CONF_DEVICE_CLASS, "")
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="configure_binary_sensor",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_configure_cover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a cover entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate unique entity name
            entity_id = user_input[CONF_NAME].lower().replace(" ", "_")
            if self._entity_index is None and any(
                e.get(CONF_ENTITY_ID) == entity_id for e in self._entities
            ):
                errors[CONF_NAME] = "entity_exists"
            else:
                # Build entity configuration
                entity_config = {
                    CONF_TYPE: ENTITY_TYPE_COVER,
                    CONF_ENTITY_ID: entity_id,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_ADS_VAR: user_input[CONF_ADS_VAR],
                }
                
                # Add optional fields
                if user_input.get(CONF_ADS_VAR_POSITION):
                    entity_config[CONF_ADS_VAR_POSITION] = user_input[
                        CONF_ADS_VAR_POSITION
                    ]
                if user_input.get(CONF_ADS_VAR_SET_POSITION):
                    entity_config[CONF_ADS_VAR_SET_POSITION] = user_input[
                        CONF_ADS_VAR_SET_POSITION
                    ]
                if user_input.get(CONF_ADS_VAR_OPEN):
                    entity_config[CONF_ADS_VAR_OPEN] = user_input[CONF_ADS_VAR_OPEN]
                if user_input.get(CONF_ADS_VAR_CLOSE):
                    entity_config[CONF_ADS_VAR_CLOSE] = user_input[CONF_ADS_VAR_CLOSE]
                if user_input.get(CONF_ADS_VAR_STOP):
                    entity_config[CONF_ADS_VAR_STOP] = user_input[CONF_ADS_VAR_STOP]
                if user_input.get(CONF_DEVICE_CLASS):
                    entity_config[CONF_DEVICE_CLASS] = user_input[CONF_DEVICE_CLASS]
                
                if self._entity_index is not None:
                    # Edit existing entity
                    self._entities[self._entity_index] = entity_config
                else:
                    # Add new entity
                    self._entities.append(entity_config)
                
                # Reset state and go back to menu
                self._entity_to_edit = None
                self._entity_index = None
                return await self.async_step_init()

        # Get defaults for edit mode
        defaults = {}
        if self._entity_to_edit and self._entity_index is not None:
            defaults = {
                CONF_NAME: self._entity_to_edit.get(CONF_NAME, ""),
                CONF_ADS_VAR: self._entity_to_edit.get(CONF_ADS_VAR, ""),
                CONF_ADS_VAR_POSITION: self._entity_to_edit.get(
                    CONF_ADS_VAR_POSITION, ""
                ),
                CONF_ADS_VAR_SET_POSITION: self._entity_to_edit.get(
                    CONF_ADS_VAR_SET_POSITION, ""
                ),
                CONF_ADS_VAR_OPEN: self._entity_to_edit.get(CONF_ADS_VAR_OPEN, ""),
                CONF_ADS_VAR_CLOSE: self._entity_to_edit.get(CONF_ADS_VAR_CLOSE, ""),
                CONF_ADS_VAR_STOP: self._entity_to_edit.get(CONF_ADS_VAR_STOP, ""),
                CONF_DEVICE_CLASS: self._entity_to_edit.get(CONF_DEVICE_CLASS, ""),
            }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): cv.string,
                vol.Required(
                    CONF_ADS_VAR, default=defaults.get(CONF_ADS_VAR, "")
                ): cv.string,
                vol.Optional(
                    CONF_ADS_VAR_POSITION,
                    default=defaults.get(CONF_ADS_VAR_POSITION, ""),
                ): cv.string,
                vol.Optional(
                    CONF_ADS_VAR_SET_POSITION,
                    default=defaults.get(CONF_ADS_VAR_SET_POSITION, ""),
                ): cv.string,
                vol.Optional(
                    CONF_ADS_VAR_OPEN, default=defaults.get(CONF_ADS_VAR_OPEN, "")
                ): cv.string,
                vol.Optional(
                    CONF_ADS_VAR_CLOSE, default=defaults.get(CONF_ADS_VAR_CLOSE, "")
                ): cv.string,
                vol.Optional(
                    CONF_ADS_VAR_STOP, default=defaults.get(CONF_ADS_VAR_STOP, "")
                ): cv.string,
                vol.Optional(
                    CONF_DEVICE_CLASS, default=defaults.get(CONF_DEVICE_CLASS, "")
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="configure_cover",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_edit_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select an entity to edit."""
        errors: dict[str, str] = {}

        if not self._entities:
            return await self.async_step_init()

        if user_input is not None:
            selected_id = user_input["entity_to_edit"]
            # Find the entity by ID
            for idx, entity in enumerate(self._entities):
                if entity.get(CONF_ENTITY_ID) == selected_id:
                    self._entity_index = idx
                    self._entity_to_edit = entity
                    
                    # Route to appropriate configuration step
                    entity_type = entity.get(CONF_TYPE)
                    if entity_type == ENTITY_TYPE_SWITCH:
                        return await self.async_step_configure_switch()
                    if entity_type == ENTITY_TYPE_LIGHT:
                        return await self.async_step_configure_light()
                    if entity_type == ENTITY_TYPE_SENSOR:
                        return await self.async_step_configure_sensor()
                    if entity_type == ENTITY_TYPE_BINARY_SENSOR:
                        return await self.async_step_configure_binary_sensor()
                    if entity_type == ENTITY_TYPE_COVER:
                        return await self.async_step_configure_cover()
                    break

        # Build entity selection dict
        entity_choices = {
            entity.get(CONF_ENTITY_ID): f"{entity.get(CONF_NAME)} ({entity.get(CONF_TYPE)})"
            for entity in self._entities
        }

        data_schema = vol.Schema(
            {
                vol.Required("entity_to_edit"): vol.In(entity_choices),
            }
        )

        return self.async_show_form(
            step_id="edit_entity",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_remove_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove an entity."""
        errors: dict[str, str] = {}

        if not self._entities:
            return await self.async_step_init()

        if user_input is not None:
            selected_id = user_input["entity_to_remove"]
            # Remove the entity by ID
            self._entities = [
                e for e in self._entities if e.get(CONF_ENTITY_ID) != selected_id
            ]
            return await self.async_step_init()

        # Build entity selection dict
        entity_choices = {
            entity.get(CONF_ENTITY_ID): f"{entity.get(CONF_NAME)} ({entity.get(CONF_TYPE)})"
            for entity in self._entities
        }

        data_schema = vol.Schema(
            {
                vol.Required("entity_to_remove"): vol.In(entity_choices),
            }
        )

        return self.async_show_form(
            step_id="remove_entity",
            data_schema=data_schema,
            errors=errors,
        )
