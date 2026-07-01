"""Coordinators for the Qingping CGD1: passive advertisements and active control."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from qingping_cgd1.client import QingpingCGD1Client
from qingping_cgd1.exceptions import AuthError, QingpingError

from .const import (
    CONF_SYNC_TIME_ON_CONNECT,
    CONF_TOKEN,
    DEFAULT_NAME,
    DEFAULT_SYNC_TIME_ON_CONNECT,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from qingping_cgd1.models import Alarm, DeviceSettings

_LOGGER = logging.getLogger(__name__)

type QingpingConfigEntry = ConfigEntry[QingpingData]


@dataclass
class QingpingData:
    """Everything a config entry hangs on to at runtime."""

    passive: QingpingPassiveCoordinator
    control: QingpingControlCoordinator


class QingpingPassiveCoordinator(
    PassiveBluetoothProcessorCoordinator[BluetoothServiceInfoBleak]
):
    """Forwards CGD1 advertisements to the sensor processor unparsed."""

    def __init__(self, hass: HomeAssistant, entry: QingpingConfigEntry) -> None:
        """Bind the coordinator to the device address in the entry."""
        super().__init__(
            hass,
            _LOGGER,
            address=entry.data[CONF_ADDRESS],
            mode=BluetoothScanningMode.PASSIVE,
            update_method=lambda service_info: service_info,
        )


@dataclass(frozen=True, slots=True)
class QingpingControlData:
    """The last-read control state of the device."""

    settings: DeviceSettings
    alarms: list[Alarm]
    firmware: str | None


class QingpingControlCoordinator(DataUpdateCoordinator[QingpingControlData]):
    """Reads and writes settings and alarms over an on-demand connection."""

    config_entry: QingpingConfigEntry

    def __init__(self, hass: HomeAssistant, entry: QingpingConfigEntry) -> None:
        """Initialise from the entry's address and token."""
        # No polling: the passive path keeps sensors fresh, and control state
        # only changes when we write it, so we refresh explicitly after writes.
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=None, config_entry=entry
        )
        self.address: str = entry.data[CONF_ADDRESS]
        self._token: bytes = bytes.fromhex(entry.data[CONF_TOKEN])
        # Read once per (re)load; the options-update listener reloads the entry
        # so a change takes effect without a restart.
        self.sync_on_connect: bool = entry.options.get(
            CONF_SYNC_TIME_ON_CONNECT, DEFAULT_SYNC_TIME_ON_CONNECT
        )

    @property
    def device_info(self) -> DeviceInfo:
        """The single device grouping every CGD1 entity."""
        # DataUpdateCoordinator types `data` as non-optional even though it is
        # `None` until the first refresh completes; entities can be set up
        # before that refresh runs, so the `None` case is real at runtime.
        if self.data is not None:  # noqa: SIM108 -- ternary trips mypy's redundant-expr
            firmware = self.data.firmware
        else:
            firmware = None  # type: ignore[unreachable]
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self.address)},
            identifiers={(DOMAIN, self.address)},
            name=DEFAULT_NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=firmware,
        )

    async def _async_update_data(self) -> QingpingControlData:
        """Connect, read the full control state, then auto-disconnect."""
        client = self._client()
        try:
            async with client:
                settings = await client.read_settings()
                alarms = await client.read_alarms()
                info = await client.read_firmware()
                # Sync while the link is already open; the client compensates for
                # the connect delay. Gated by the options-flow toggle.
                if self.sync_on_connect:
                    await client.sync_time()
        except AuthError as err:
            # The clock has been re-paired to another app or token; HA turns
            # this into a reauth flow on the config entry.
            raise ConfigEntryAuthFailed(str(err)) from err
        except QingpingError as err:
            raise UpdateFailed(str(err)) from err
        return QingpingControlData(
            settings=settings, alarms=alarms, firmware=info.firmware
        )

    async def async_update_settings(self, **changes: Any) -> None:
        """Replace fields on the last-read settings and write them back."""
        current = self._require_data().settings
        updated = dataclasses.replace(current, **changes)
        await self._write(lambda client: client.write_settings(updated))

    async def async_write_alarm(self, slot: int, alarm: Alarm) -> None:
        """Write a single alarm slot."""
        await self._write(lambda client: client.write_alarm(slot, alarm))

    async def async_delete_alarm(self, slot: int) -> None:
        """Clear a single alarm slot."""
        await self._write(lambda client: client.delete_alarm(slot))

    async def async_sync_time(self) -> None:
        """Push the current time to the device."""
        await self._write(lambda client: client.sync_time())

    def _client(self) -> QingpingCGD1Client:
        device = async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            msg = f"{self.address} is not currently reachable over Bluetooth"
            raise UpdateFailed(msg)
        return QingpingCGD1Client(device, self._token)

    def _require_data(self) -> QingpingControlData:
        # See device_info: `data` is really optional pre-refresh despite the
        # base class's non-optional type.
        if self.data is None:
            msg = "The device has not been read yet"  # type: ignore[unreachable]
            raise HomeAssistantError(msg)
        return self.data

    async def _write(
        self, action: Callable[[QingpingCGD1Client], Awaitable[None]]
    ) -> None:
        client = self._client()
        try:
            async with client:
                await action(client)
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except QingpingError as err:
            raise HomeAssistantError(str(err)) from err
        await self.async_request_refresh()
