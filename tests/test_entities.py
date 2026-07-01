"""Entity tests across the platforms."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from freezegun import freeze_time
from homeassistant.const import EntityCategory
from qingping_cgd1.codec import next_alarm

from tests.conftest import (
    inject_service_info,
    make_service_info,
    sample_alarms,
    sample_settings,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

TEMP = "sensor.qingping_alarm_clock_temperature"
HUMIDITY = "sensor.qingping_alarm_clock_humidity"
BATTERY = "sensor.qingping_alarm_clock_battery"
SIGNAL = "sensor.qingping_alarm_clock_signal_strength"
FIRMWARE = "sensor.qingping_alarm_clock_firmware"
NEXT_ALARM = "sensor.qingping_alarm_clock_next_alarm"
VOLUME = "number.qingping_alarm_clock_volume"
DAY_BRIGHTNESS = "number.qingping_alarm_clock_day_brightness"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_passive_sensors_from_advertisement(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """An injected fdcd advertisement drives temperature, humidity, battery, signal."""
    await _setup(hass, mock_entry)
    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done()

    assert hass.states.get(TEMP).state == "20.0"
    assert hass.states.get(HUMIDITY).state == "51.7"
    assert hass.states.get(BATTERY).state == "80"
    assert hass.states.get(SIGNAL).state == "-58"


async def test_firmware_sensor_is_diagnostic(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """The firmware sensor reports the read version and is a diagnostic entity."""
    await _setup(hass, mock_entry)

    state = hass.states.get(FIRMWARE)
    assert state is not None
    assert state.state == "1.2.3"

    registry = hass.data["entity_registry"]  # er.async_get(hass) equivalent
    entry = registry.async_get(FIRMWARE)
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@freeze_time("2026-07-01 03:00:00")
async def test_next_alarm_sensor(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """The next-alarm sensor surfaces the library result in device-local time."""
    await _setup(hass, mock_entry)

    device_tz = timezone(timedelta(minutes=sample_settings().tz_offset_minutes))
    now = datetime(2026, 7, 1, 3, 0, tzinfo=UTC).astimezone(device_tz)
    expected = next_alarm(sample_alarms(), now)

    state = hass.states.get(NEXT_ALARM)
    assert state is not None
    assert datetime.fromisoformat(state.state) == expected


async def test_number_reads_setting(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Volume reflects the read settings blob."""
    await _setup(hass, mock_entry)
    assert hass.states.get(VOLUME).state == "3.0"
    assert hass.states.get(DAY_BRIGHTNESS).state == "80.0"


async def test_number_write_updates_setting(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Setting volume writes a replaced settings blob."""
    await _setup(hass, mock_entry)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": VOLUME, "value": 5},
        blocking=True,
    )
    written = mock_client.write_settings.await_args.args[0]
    assert written.volume == 5
