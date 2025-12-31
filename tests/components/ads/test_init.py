"""Tests for the ADS integration init."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.ads import async_setup
from homeassistant.components.ads.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


async def test_async_setup_no_config(hass: HomeAssistant) -> None:
    """Test async_setup returns True when no YAML config is provided.

    This tests the fix for KeyError 'ads' when the domain is not in config.
    """
    # Empty config - no 'ads' domain
    config = {}
    result = await async_setup(hass, config)
    assert result is True


async def test_async_setup_with_config(hass: HomeAssistant) -> None:
    """Test async_setup initiates import flow when YAML config is provided."""
    config = {
        DOMAIN: {
            CONF_DEVICE: "1.2.3.4.5.6",
            CONF_PORT: 48898,
            CONF_IP_ADDRESS: "192.168.1.100",
        }
    }

    with patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        result = await async_setup(hass, config)
        await hass.async_block_till_done()

        assert result is True
        # Verify import flow was initiated
        mock_init.assert_called_once()
        call_args = mock_init.call_args
        assert call_args[0][0] == DOMAIN
        assert call_args[1]["context"]["source"] == "import"
        assert call_args[1]["data"][CONF_DEVICE] == "1.2.3.4.5.6"
        assert call_args[1]["data"][CONF_PORT] == 48898


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE: "1.2.3.4.5.6",
            CONF_PORT: 48898,
            CONF_IP_ADDRESS: "192.168.1.100",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.ads.pyads.Connection") as mock_client,
        patch("homeassistant.components.ads.hub.AdsHub") as mock_hub,
    ):
        client = MagicMock()
        mock_client.return_value = client

        hub = MagicMock()
        hub.connected = True
        hub.check_connection = MagicMock(return_value=True)
        mock_hub.return_value = hub

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_connection_error(hass: HomeAssistant) -> None:
    """Test setup fails when connection is not available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE: "1.2.3.4.5.6",
            CONF_PORT: 48898,
            CONF_IP_ADDRESS: "192.168.1.100",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.ads.pyads.Connection") as mock_client,
        patch("homeassistant.components.ads.hub.AdsHub") as mock_hub,
    ):
        client = MagicMock()
        mock_client.return_value = client

        hub = MagicMock()
        hub.connected = False
        hub.check_connection = MagicMock(return_value=False)
        mock_hub.return_value = hub

        with pytest.raises(ConfigEntryNotReady):
            await hass.config_entries.async_setup(entry.entry_id)

        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE: "1.2.3.4.5.6",
            CONF_PORT: 48898,
            CONF_IP_ADDRESS: "192.168.1.100",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.ads.pyads.Connection") as mock_client,
        patch("homeassistant.components.ads.hub.AdsHub") as mock_hub,
    ):
        client = MagicMock()
        mock_client.return_value = client

        hub = MagicMock()
        hub.connected = True
        hub.check_connection = MagicMock(return_value=True)
        hub.shutdown = MagicMock()
        mock_hub.return_value = hub

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED
        hub.shutdown.assert_called_once()
