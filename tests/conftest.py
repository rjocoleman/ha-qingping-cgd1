"""Shared fixtures and BLE injection helpers for the Qingping CGD1 tests."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from home_assistant_bluetooth import BluetoothServiceInfoBleak
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from qingping_cgd1.models import Alarm, DeviceInfo, DeviceSettings, Language, Weekday

from custom_components.qingping_cgd1.const import CONF_TOKEN, DOMAIN
from qingping_cgd1.const import DEFAULT_AUTH_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import HomeAssistant

# Real fdcd advertisement, captured from a real CGD1 (firmware 1.0.1_0130):
# frame byte, model 0x0c, 6-byte MAC, 2 unknown bytes, temp int16 LE /10,
# humidity uint16 LE /10, 2 unknown bytes, battery percent. 200 -> 20.0 C,
# 517 -> 51.7 %, 0x50 -> 80 %.
MAC = "58:2D:34:12:34:56"
FDCD_ADV = bytes.fromhex("880c523886342d580104c8000502020150")
ALARM_SLOT_COUNT = 16


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations: object) -> None:
    """Load the custom integration in every test."""
    return


@pytest.fixture(autouse=True)
def _no_core_bluetooth_matchers() -> Iterator[None]:
    """Stop real advertisements from also matching core HA integrations.

    The CGD1's fdcd service data is the same one the built-in `qingping`
    integration matches on. Letting real discovery run against the full
    core matcher list starts that integration's config flow too, which
    needs a dependency (`qingping-ble`) this project doesn't install. Our
    own domain's matcher is added separately from this custom component's
    manifest, so clearing the core list only removes the collision.
    """
    with patch("homeassistant.loader.BLUETOOTH", []):
        yield


@pytest.fixture
def expected_lingering_timers() -> bool:
    """Allow the periodic device-expiry timer `enable_bluetooth` leaves behind.

    `homeassistant.components.bluetooth.async_setup_entry` discards the
    unsub callback that `HaScanner.async_setup()` returns, so the scanner's
    `_async_expire_devices_schedule_next` timer is never cancelled when the
    fixture unloads its config entry. Reproduces with `enable_bluetooth`
    alone, with no code from this integration involved, on
    homeassistant==2026.6.3 / habluetooth==6.26.0, so it is an upstream gap
    rather than something to chase down here.
    """
    return True


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """A configured entry keyed on the device MAC."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_ADDRESS: MAC, CONF_TOKEN: DEFAULT_AUTH_TOKEN.hex()},
    )


def make_service_info(
    *, address: str = MAC, rssi: int = -58, service_data: bytes | None = None
) -> BluetoothServiceInfoBleak:
    """Build a CGD1 advertisement carrying fdcd service data."""
    raw = FDCD_ADV if service_data is None else service_data
    from custom_components.qingping_cgd1.const import SERVICE_DATA_UUID  # noqa: PLC0415

    device = BLEDevice(address, DEFAULT_NAME_LOCAL, {})
    payload = {SERVICE_DATA_UUID: raw}
    adv = AdvertisementData(
        local_name=DEFAULT_NAME_LOCAL,
        manufacturer_data={},
        service_data=payload,
        service_uuids=[SERVICE_DATA_UUID],
        tx_power=-127,
        rssi=rssi,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name=DEFAULT_NAME_LOCAL,
        address=address,
        rssi=rssi,
        manufacturer_data={},
        service_data=payload,
        service_uuids=[SERVICE_DATA_UUID],
        source="local",
        device=device,
        advertisement=adv,
        connectable=True,
        time=0.0,
        tx_power=-127,
    )


DEFAULT_NAME_LOCAL = "Qingping Alarm Clock"


def inject_service_info(hass: HomeAssistant, info: BluetoothServiceInfoBleak) -> None:
    """Feed an advertisement into the bluetooth manager as a scanner would.

    pytest-homeassistant-custom-component==0.13.339 does not ship an
    `inject_bluetooth_service_info` helper, so this repo provides its own,
    built on `bluetooth.async_get_advertisement_callback`. This is intentional,
    not an oversight.
    """
    bluetooth.async_get_advertisement_callback(hass)(info)


def sample_settings() -> DeviceSettings:
    """A representative settings blob covering every control field."""
    return DeviceSettings(
        volume=3,
        language=Language.ENGLISH,
        time_format_24h=True,
        unit_celsius=True,
        alarms_enabled=True,
        tz_offset_minutes=780,
        screen_light_seconds=10,
        day_brightness=80,
        night_brightness=20,
        night_start=time(22, 0),
        night_end=time(7, 0),
        night_mode=True,
        ringtone_signature=b"\x00\x00\x00\x01",
        raw_reserved=b"\x58\x02\x00",
    )


def sample_alarms() -> list[Alarm]:
    """Slot 0 and 1 in use, the rest empty."""
    alarms = [Alarm.empty() for _ in range(ALARM_SLOT_COUNT)]
    alarms[0] = Alarm(
        enabled=True,
        hour=7,
        minute=30,
        days=frozenset({Weekday.MONDAY, Weekday.FRIDAY}),
        snooze=False,
    )
    alarms[1] = Alarm(enabled=True, hour=8, minute=0, days=frozenset(), snooze=True)
    return alarms


@pytest.fixture
def mock_client() -> Iterator[MagicMock]:
    """Patch the control client and BLE lookup with a canned fake.

    The client is an async context manager; reads return the sample data and
    writes are AsyncMocks the tests assert against.
    """
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    # connect/disconnect are exercised directly by the config flow's
    # connect-and-authenticate check, outside the async-context-manager path.
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.read_settings = AsyncMock(return_value=sample_settings())
    client.read_alarms = AsyncMock(return_value=sample_alarms())
    client.read_firmware = AsyncMock(return_value=DeviceInfo(firmware="1.2.3"))
    client.write_settings = AsyncMock()
    client.write_alarm = AsyncMock()
    client.delete_alarm = AsyncMock()
    client.sync_time = AsyncMock()

    with (
        patch(
            "custom_components.qingping_cgd1.coordinator.QingpingCGD1Client",
            return_value=client,
        ),
        patch(
            "custom_components.qingping_cgd1.coordinator.async_ble_device_from_address",
            return_value=MagicMock(spec=BLEDevice),
        ),
        # The config flow's connect-and-authenticate check builds its own
        # client and BLE lookup, independent of the coordinator's.
        patch(
            "custom_components.qingping_cgd1.config_flow.QingpingCGD1Client",
            return_value=client,
        ),
        patch(
            "custom_components.qingping_cgd1.config_flow.async_ble_device_from_address",
            return_value=MagicMock(spec=BLEDevice),
        ),
    ):
        yield client
