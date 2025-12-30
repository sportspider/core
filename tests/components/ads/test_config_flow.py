"""Tests for the ADS config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pyads
import pytest

from homeassistant import config_entries
from homeassistant.components.ads.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_DEVICE: "1.2.3.4.5.6",
    CONF_PORT: 48898,
    CONF_IP_ADDRESS: "192.168.1.100",
}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_invalid_net_id(hass: HomeAssistant) -> None:
    """Test we show error on invalid Net ID format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_DEVICE: "invalid",
            CONF_PORT: 48898,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_net_id"}


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on ADS connection error."""
    with patch(
        "homeassistant.components.ads.config_flow.pyads.Connection"
    ) as mock_client:
        client = MagicMock()
        client.open = MagicMock(side_effect=pyads.ADSError)
        mock_client.return_value = client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_full_flow(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""
    with patch(
        "homeassistant.components.ads.config_flow.pyads.Connection"
    ) as mock_client:
        client = MagicMock()
        client.open = MagicMock()
        client.read_state = MagicMock()
        client.close = MagicMock()
        mock_client.return_value = client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "ADS 1.2.3.4.5.6 (192.168.1.100)"
        assert result["data"] == FIXTURE_USER_INPUT


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test that duplicate entries are rejected."""
    # Create first entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=FIXTURE_USER_INPUT,
    )
    entry.add_to_hass(hass)

    # Try to create duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=FIXTURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test import from YAML configuration."""
    with patch(
        "homeassistant.components.ads.config_flow.pyads.Connection"
    ) as mock_client:
        client = MagicMock()
        client.open = MagicMock()
        client.read_state = MagicMock()
        client.close = MagicMock()
        mock_client.return_value = client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=FIXTURE_USER_INPUT,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "ADS 1.2.3.4.5.6 (192.168.1.100)"
        assert result["data"] == FIXTURE_USER_INPUT


async def test_import_flow_connection_error(hass: HomeAssistant) -> None:
    """Test import aborts on connection error."""
    with patch(
        "homeassistant.components.ads.config_flow.pyads.Connection"
    ) as mock_client:
        client = MagicMock()
        client.open = MagicMock(side_effect=pyads.ADSError)
        mock_client.return_value = client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=FIXTURE_USER_INPUT,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguring an existing entry."""
    # Create existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=FIXTURE_USER_INPUT,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ads.config_flow.pyads.Connection"
    ) as mock_client:
        client = MagicMock()
        client.open = MagicMock()
        client.read_state = MagicMock()
        client.close = MagicMock()
        mock_client.return_value = client

        # Start reconfiguration
        result = await entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        # Update configuration
        new_data = {
            CONF_DEVICE: "1.2.3.4.5.6",
            CONF_PORT: 12345,
            CONF_IP_ADDRESS: "192.168.1.200",
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=new_data,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data == new_data


async def test_options_flow_add_switch(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a switch through options flow."""
    mock_config_entry.add_to_hass(hass)
    
    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    
    # Select add_entity
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_entity"},
    )
    
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_entity"
    
    # Select switch type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"type": "switch"},
    )
    
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_switch"
    
    # Configure switch
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "Test Switch", "adsvar": "GVL.bSwitch1"},
    )
    
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    
    # Finish configuration
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "finish"},
    )
    
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "entities" in result["data"]
    assert len(result["data"]["entities"]) == 1
    assert result["data"]["entities"][0]["type"] == "switch"
    assert result["data"]["entities"][0]["name"] == "Test Switch"
    assert result["data"]["entities"][0]["adsvar"] == "GVL.bSwitch1"


async def test_options_flow_add_light(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a light through options flow."""
    mock_config_entry.add_to_hass(hass)
    
    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    
    # Select add_entity
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_entity"},
    )
    
    # Select light type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"type": "light"},
    )
    
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_light"
    
    # Configure light with brightness
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Test Light",
            "adsvar": "GVL.bLight1",
            "adsvar_brightness": "GVL.nBrightness1",
        },
    )
    
    assert result["type"] is FlowResultType.MENU
    
    # Finish
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "finish"},
    )
    
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(result["data"]["entities"]) == 1
    assert result["data"]["entities"][0]["type"] == "light"
    assert result["data"]["entities"][0]["adsvar_brightness"] == "GVL.nBrightness1"


async def test_options_flow_add_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a sensor through options flow."""
    mock_config_entry.add_to_hass(hass)
    
    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    
    # Navigate to add sensor
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_entity"},
    )
    
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"type": "sensor"},
    )
    
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_sensor"
    
    # Configure sensor
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Temperature",
            "adsvar": "GVL.fTemp1",
            "adstype": "real",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
        },
    )
    
    # Finish
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "finish"},
    )
    
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(result["data"]["entities"]) == 1
    entity = result["data"]["entities"][0]
    assert entity["type"] == "sensor"
    assert entity["adstype"] == "real"
    assert entity["unit_of_measurement"] == "°C"


async def test_options_flow_edit_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test editing an entity through options flow."""
    # Add entity to options
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            "entities": [
                {
                    "type": "switch",
                    "entity_id": "test_switch",
                    "name": "Test Switch",
                    "adsvar": "GVL.bSwitch1",
                }
            ]
        },
    )
    
    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    
    # Select edit_entity
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "edit_entity"},
    )
    
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "edit_entity"
    
    # Select entity to edit
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"entity_to_edit": "test_switch"},
    )
    
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_switch"
    
    # Update entity
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "Updated Switch", "adsvar": "GVL.bSwitch2"},
    )
    
    # Finish
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "finish"},
    )
    
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(result["data"]["entities"]) == 1
    assert result["data"]["entities"][0]["name"] == "Updated Switch"
    assert result["data"]["entities"][0]["adsvar"] == "GVL.bSwitch2"


async def test_options_flow_remove_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test removing an entity through options flow."""
    # Add entities to options
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            "entities": [
                {
                    "type": "switch",
                    "entity_id": "switch1",
                    "name": "Switch 1",
                    "adsvar": "GVL.bSwitch1",
                },
                {
                    "type": "switch",
                    "entity_id": "switch2",
                    "name": "Switch 2",
                    "adsvar": "GVL.bSwitch2",
                },
            ]
        },
    )
    
    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    
    # Select remove_entity
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove_entity"},
    )
    
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "remove_entity"
    
    # Select entity to remove
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"entity_to_remove": "switch1"},
    )
    
    assert result["type"] is FlowResultType.MENU
    
    # Finish
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "finish"},
    )
    
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(result["data"]["entities"]) == 1
    assert result["data"]["entities"][0]["entity_id"] == "switch2"


async def test_options_flow_duplicate_entity_name(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that duplicate entity names are rejected."""
    # Add entity to options
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            "entities": [
                {
                    "type": "switch",
                    "entity_id": "test_switch",
                    "name": "Test Switch",
                    "adsvar": "GVL.bSwitch1",
                }
            ]
        },
    )
    
    # Start options flow and try to add duplicate
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_entity"},
    )
    
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"type": "switch"},
    )
    
    # Try to add entity with same name
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "Test Switch", "adsvar": "GVL.bSwitch2"},
    )
    
    # Should show error
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"name": "entity_exists"}
