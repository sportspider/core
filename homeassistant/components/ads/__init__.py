"""Support for Automation Device Specification (ADS)."""

from __future__ import annotations

import logging

import pyads
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ADS_VAR, DATA_ADS, DOMAIN, AdsType
from .hub import AdsHub

_LOGGER = logging.getLogger(__name__)


ADS_TYPEMAP = {
    AdsType.BOOL: pyads.PLCTYPE_BOOL,
    AdsType.BYTE: pyads.PLCTYPE_BYTE,
    AdsType.INT: pyads.PLCTYPE_INT,
    AdsType.UINT: pyads.PLCTYPE_UINT,
    AdsType.SINT: pyads.PLCTYPE_SINT,
    AdsType.USINT: pyads.PLCTYPE_USINT,
    AdsType.DINT: pyads.PLCTYPE_DINT,
    AdsType.UDINT: pyads.PLCTYPE_UDINT,
    AdsType.WORD: pyads.PLCTYPE_WORD,
    AdsType.DWORD: pyads.PLCTYPE_DWORD,
    AdsType.REAL: pyads.PLCTYPE_REAL,
    AdsType.LREAL: pyads.PLCTYPE_LREAL,
    AdsType.STRING: pyads.PLCTYPE_STRING,
    AdsType.TIME: pyads.PLCTYPE_TIME,
    AdsType.DATE: pyads.PLCTYPE_DATE,
    AdsType.DATE_AND_TIME: pyads.PLCTYPE_DT,
    AdsType.TOD: pyads.PLCTYPE_TOD,
}

CONF_ADS_FACTOR = "factor"
CONF_ADS_TYPE = "adstype"
CONF_ADS_VALUE = "value"


SERVICE_WRITE_DATA_BY_NAME = "write_data_by_name"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DEVICE): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Optional(CONF_IP_ADDRESS): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_SERVICE_WRITE_DATA_BY_NAME = vol.Schema(
    {
        vol.Required(CONF_ADS_TYPE): vol.Coerce(AdsType),
        vol.Required(CONF_ADS_VALUE): vol.Coerce(int),
        vol.Required(CONF_ADS_VAR): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component."""
    # Check if YAML configuration exists
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    # Import YAML config to config entry
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={
                CONF_DEVICE: conf[CONF_DEVICE],
                CONF_PORT: conf[CONF_PORT],
                CONF_IP_ADDRESS: conf.get(CONF_IP_ADDRESS),
            },
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ADS from a config entry."""
    net_id = entry.data[CONF_DEVICE]
    port = entry.data[CONF_PORT]
    ip_address = entry.data.get(CONF_IP_ADDRESS)

    client = pyads.Connection(net_id, port, ip_address)

    # Initialize hub with connection monitoring
    ads_hub = AdsHub(client, hass)

    # Check if connected
    if not ads_hub.connected:
        # Try to connect one more time before giving up
        connected = await hass.async_add_executor_job(ads_hub.check_connection)
        if not connected:
            raise ConfigEntryNotReady(f"Could not connect to ADS device {net_id}")

    # Store hub in hass data
    hass.data[DATA_ADS] = ads_hub

    # Register shutdown handler
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, ads_hub.shutdown)
    )

    # Register service
    def handle_write_data_by_name(call: ServiceCall) -> None:
        """Write a value to the connected ADS device."""
        ads_var: str = call.data[CONF_ADS_VAR]
        ads_type: AdsType = call.data[CONF_ADS_TYPE]
        value: int = call.data[CONF_ADS_VALUE]

        result = ads_hub.write_by_name(ads_var, value, ADS_TYPEMAP[ads_type])
        if result is None:
            _LOGGER.error("Failed to write to ADS variable %s", ads_var)

    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        handle_write_data_by_name,
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME,
    )

    # Forward setup to platforms based on configured entities
    entities = entry.options.get("entities", [])
    platforms_to_load = set()

    for entity_config in entities:
        entity_type = entity_config.get("type")
        if entity_type:
            platforms_to_load.add(entity_type)

    # Always load platforms even if no entities configured yet (for future additions)
    # This allows the platforms to set up async_setup_entry which can be called later
    all_platforms = ["switch", "light", "sensor", "binary_sensor", "cover"]

    await hass.config_entries.async_forward_entry_setups(entry, all_platforms)

    # Register update listener to handle options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an ADS config entry."""
    # Unload all platforms
    all_platforms = ["switch", "light", "sensor", "binary_sensor", "cover"]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, all_platforms)

    if unload_ok:
        ads_hub: AdsHub = hass.data.get(DATA_ADS)

        if ads_hub:
            await hass.async_add_executor_job(ads_hub.shutdown)
            hass.data.pop(DATA_ADS, None)

        # Remove service if this is the last entry
        if not hass.config_entries.async_loaded_entries(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_WRITE_DATA_BY_NAME)

    return unload_ok
