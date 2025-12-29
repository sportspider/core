"""Common fixtures for ADS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pyads
import pytest

from homeassistant.components.ads.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ads.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_ads_client():
    """Mock pyads.Connection."""
    with patch("homeassistant.components.ads.config_flow.pyads.Connection") as mock_client:
        client = MagicMock()
        client.open = MagicMock()
        client.read_state = MagicMock()
        client.close = MagicMock()
        mock_client.return_value = client
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE: "1.2.3.4.5.6",
            CONF_PORT: 48898,
            CONF_IP_ADDRESS: "192.168.1.100",
        },
        title="ADS 1.2.3.4.5.6 (192.168.1.100)",
    )
