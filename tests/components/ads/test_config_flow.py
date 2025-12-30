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
