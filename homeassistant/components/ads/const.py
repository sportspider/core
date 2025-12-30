"""Support for Automation Device Specification (ADS)."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .hub import AdsHub

DOMAIN = "ads"

DATA_ADS: HassKey[AdsHub] = HassKey(DOMAIN)

CONF_ADS_VAR = "adsvar"

STATE_KEY_STATE = "state"

# Connection monitoring constants
CONF_ADS_VAR_MONITORED = "ads_var_monitored"
DEFAULT_PORT = 48898
CONNECTION_RETRY_INTERVAL = [1, 2, 4, 8, 16, 32, 60]  # Exponential backoff in seconds


class AdsType(StrEnum):
    """Supported Types."""

    BOOL = "bool"
    BYTE = "byte"
    INT = "int"
    UINT = "uint"
    SINT = "sint"
    USINT = "usint"
    DINT = "dint"
    UDINT = "udint"
    WORD = "word"
    DWORD = "dword"
    LREAL = "lreal"
    REAL = "real"
    STRING = "string"
    TIME = "time"
    DATE = "date"
    DATE_AND_TIME = "dt"
    TOD = "tod"
