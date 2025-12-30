"""Support for Automation Device Specification (ADS)."""

import asyncio
from collections import namedtuple
from collections.abc import Callable
import ctypes
import logging
import struct
import threading

import pyads

from .const import CONNECTION_RETRY_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Tuple to hold data needed for notification
NotificationItem = namedtuple(  # noqa: PYI024
    "NotificationItem", "hnotify huser name plc_datatype callback"
)


class AdsHub:
    """Representation of an ADS connection."""

    def __init__(self, ads_client, hass=None):
        """Initialize the ADS hub."""
        self._client = ads_client
        self._hass = hass
        self._connected = False
        self._connection_callbacks: list[Callable[[bool], None]] = []
        self._reconnect_task = None
        self._retry_count = 0
        self._unavailable_logged = False

        # All ADS devices are registered here
        self._devices = []
        self._notification_items = {}
        self._lock = threading.Lock()

        # Try initial connection
        try:
            self._client.open()
            self._connected = True
            _LOGGER.info("Successfully connected to ADS device")
        except pyads.ADSError as err:
            _LOGGER.error("Failed to connect to ADS device: %s", err)
            self._connected = False
            if hass:
                # Schedule reconnection attempts
                self._schedule_reconnect()

    @property
    def connected(self) -> bool:
        """Return True if connected to ADS device."""
        return self._connected

    def add_connection_callback(self, callback: Callable[[bool], None]) -> None:
        """Add a callback to be called when connection state changes."""
        self._connection_callbacks.append(callback)

    def remove_connection_callback(self, callback: Callable[[bool], None]) -> None:
        """Remove a connection state callback."""
        if callback in self._connection_callbacks:
            self._connection_callbacks.remove(callback)

    def _notify_connection_state(self, connected: bool) -> None:
        """Notify all callbacks of connection state change."""
        for callback in self._connection_callbacks:
            try:
                callback(connected)
            except Exception:
                _LOGGER.exception("Error calling connection callback")

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if not self._hass or self._reconnect_task:
            return

        # Get retry interval with exponential backoff
        retry_index = min(self._retry_count, len(CONNECTION_RETRY_INTERVAL) - 1)
        retry_interval = CONNECTION_RETRY_INTERVAL[retry_index]

        _LOGGER.debug("Scheduling reconnection in %s seconds", retry_interval)

        async def reconnect_async():
            """Reconnect to ADS device."""
            await asyncio.sleep(retry_interval)
            self._reconnect_task = None
            await self._hass.async_add_executor_job(self._try_reconnect)

        self._reconnect_task = self._hass.async_create_task(reconnect_async())

    def _try_reconnect(self) -> None:
        """Try to reconnect to ADS device."""
        try:
            if not self._connected:
                self._client.open()
                # Test connection by reading state
                self._client.read_state()
                self._connected = True
                self._retry_count = 0
                _LOGGER.info("Reconnected to ADS device")
                if self._unavailable_logged:
                    _LOGGER.info("ADS device is back online")
                    self._unavailable_logged = False
                self._notify_connection_state(True)
        except pyads.ADSError as err:
            _LOGGER.debug("Reconnection attempt failed: %s", err)
            self._retry_count += 1
            self._connected = False
            if not self._unavailable_logged:
                _LOGGER.info("ADS device is unavailable: %s", err)
                self._unavailable_logged = True
            # Schedule next reconnection attempt
            if self._hass:
                self._schedule_reconnect()

    def check_connection(self) -> bool:
        """Check if connection to ADS device is still alive."""
        with self._lock:
            try:
                self._client.read_state()
                if not self._connected:
                    self._connected = True
                    self._retry_count = 0
                    _LOGGER.info("ADS connection restored")
                    if self._unavailable_logged:
                        _LOGGER.info("ADS device is back online")
                        self._unavailable_logged = False
                    self._notify_connection_state(True)
                return True
            except pyads.ADSError as err:
                if self._connected:
                    _LOGGER.error("Lost connection to ADS device: %s", err)
                    self._connected = False
                    if not self._unavailable_logged:
                        _LOGGER.info("ADS device is unavailable: %s", err)
                        self._unavailable_logged = True
                    self._notify_connection_state(False)
                    if self._hass:
                        self._schedule_reconnect()
                return False

    def shutdown(self, *args, **kwargs):
        """Shutdown ADS connection."""
        _LOGGER.debug("Shutting down ADS")

        # Cancel reconnection task if scheduled
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        for notification_item in self._notification_items.values():
            _LOGGER.debug(
                "Deleting device notification %d, %d",
                notification_item.hnotify,
                notification_item.huser,
            )
            try:
                self._client.del_device_notification(
                    notification_item.hnotify, notification_item.huser
                )
            except pyads.ADSError as err:
                _LOGGER.error(err)
        try:
            self._client.close()
            self._connected = False
        except pyads.ADSError as err:
            _LOGGER.error(err)

    def register_device(self, device):
        """Register a new device."""
        self._devices.append(device)

    def write_by_name(self, name, value, plc_datatype):
        """Write a value to the device."""
        with self._lock:
            try:
                if not self._connected:
                    _LOGGER.error("Cannot write %s: not connected", name)
                    return None
                return self._client.write_by_name(name, value, plc_datatype)
            except pyads.ADSError as err:
                _LOGGER.error("Error writing %s: %s", name, err)
                self._connected = False
                if self._hass:
                    self._schedule_reconnect()
                return None

    def read_by_name(self, name, plc_datatype):
        """Read a value from the device."""
        with self._lock:
            try:
                if not self._connected:
                    _LOGGER.error("Cannot read %s: not connected", name)
                    return None
                return self._client.read_by_name(name, plc_datatype)
            except pyads.ADSError as err:
                _LOGGER.error("Error reading %s: %s", name, err)
                self._connected = False
                if self._hass:
                    self._schedule_reconnect()
                return None

    def add_device_notification(self, name, plc_datatype, callback):
        """Add a notification to the ADS devices."""
        attr = pyads.NotificationAttrib(ctypes.sizeof(plc_datatype))

        with self._lock:
            try:
                if not self._connected:
                    _LOGGER.error("Cannot add notification for %s: not connected", name)
                    return
                hnotify, huser = self._client.add_device_notification(
                    name, attr, self._device_notification_callback
                )
            except pyads.ADSError as err:
                _LOGGER.error("Error subscribing to %s: %s", name, err)
                self._connected = False
                if self._hass:
                    self._schedule_reconnect()
            else:
                hnotify = int(hnotify)
                self._notification_items[hnotify] = NotificationItem(
                    hnotify, huser, name, plc_datatype, callback
                )

                _LOGGER.debug(
                    "Added device notification %d for variable %s", hnotify, name
                )

    def _device_notification_callback(self, notification, name):
        """Handle device notifications."""
        contents = notification.contents
        hnotify = int(contents.hNotification)
        _LOGGER.debug("Received notification %d", hnotify)

        # Get dynamically sized data array
        data_size = contents.cbSampleSize
        data_address = (
            ctypes.addressof(contents)
            + pyads.structs.SAdsNotificationHeader.data.offset
        )
        data = (ctypes.c_ubyte * data_size).from_address(data_address)

        # Acquire notification item
        with self._lock:
            notification_item = self._notification_items.get(hnotify)

        if not notification_item:
            _LOGGER.error("Unknown device notification handle: %d", hnotify)
            return

        # Data parsing based on PLC data type
        plc_datatype = notification_item.plc_datatype
        unpack_formats = {
            pyads.PLCTYPE_BYTE: "<b",
            pyads.PLCTYPE_INT: "<h",
            pyads.PLCTYPE_UINT: "<H",
            pyads.PLCTYPE_SINT: "<b",
            pyads.PLCTYPE_USINT: "<B",
            pyads.PLCTYPE_DINT: "<i",
            pyads.PLCTYPE_UDINT: "<I",
            pyads.PLCTYPE_WORD: "<H",
            pyads.PLCTYPE_DWORD: "<I",
            pyads.PLCTYPE_LREAL: "<d",
            pyads.PLCTYPE_REAL: "<f",
            pyads.PLCTYPE_TOD: "<i",  # Treat as DINT
            pyads.PLCTYPE_DATE: "<i",  # Treat as DINT
            pyads.PLCTYPE_DT: "<i",  # Treat as DINT
            pyads.PLCTYPE_TIME: "<i",  # Treat as DINT
        }

        if plc_datatype == pyads.PLCTYPE_BOOL:
            value = bool(struct.unpack("<?", bytearray(data))[0])
        elif plc_datatype == pyads.PLCTYPE_STRING:
            value = (
                bytearray(data).split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            )
        elif plc_datatype in unpack_formats:
            value = struct.unpack(unpack_formats[plc_datatype], bytearray(data))[0]
        else:
            value = bytearray(data)
            _LOGGER.warning("No callback available for this datatype")

        notification_item.callback(notification_item.name, value)
