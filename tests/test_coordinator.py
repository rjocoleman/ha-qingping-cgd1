"""Control-coordinator reads, writes and error mapping."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from freezegun import freeze_time
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from qingping_cgd1.exceptions import AuthError, QingpingError

from custom_components.qingping_cgd1.const import (
    CONF_MATCH_HA_TIMEZONE,
    CONF_SYNC_INTERVAL_HOURS,
    CONF_SYNC_TIME_ON_CONNECT,
)
from custom_components.qingping_cgd1.coordinator import QingpingControlCoordinator
from tests.conftest import MAC, sample_settings

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant


def _coordinator(
    hass: HomeAssistant, entry: MockConfigEntry
) -> QingpingControlCoordinator:
    entry.add_to_hass(hass)
    return QingpingControlCoordinator(hass, entry)


async def test_first_refresh_reads_all(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A refresh reads settings, alarms and firmware into the data model."""
    coordinator = _coordinator(hass, mock_entry)
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.settings.volume == 3
    assert len(coordinator.data.alarms) == 16
    assert coordinator.data.firmware == "1.2.3"
    assert coordinator.address == MAC


async def test_update_settings_writes_and_refreshes(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A single-field settings change writes a replaced blob then re-reads."""
    coordinator = _coordinator(hass, mock_entry)
    await coordinator.async_refresh()

    await coordinator.async_update_settings(volume=5)

    written = mock_client.write_settings.await_args.args[0]
    assert written == dataclasses.replace(sample_settings(), volume=5)
    assert mock_client.read_settings.await_count == 2


async def test_no_device_raises_update_failed(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """When the device is not reachable a refresh fails softly."""
    coordinator = _coordinator(hass, mock_entry)
    with (
        patch(
            "custom_components.qingping_cgd1.coordinator.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_library_error_becomes_update_failed(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A library QingpingError during a read maps to UpdateFailed."""
    mock_client.read_settings.side_effect = QingpingError("boom")
    coordinator = _coordinator(hass, mock_entry)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_auth_error_becomes_config_entry_auth_failed(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """An AuthError during a read maps to ConfigEntryAuthFailed, which starts reauth.

    Hardware-confirmed: a clock re-paired to another app or token fails the
    auth handshake at runtime, not just at initial setup.
    """
    mock_client.read_settings.side_effect = AuthError("clock is bound elsewhere")
    coordinator = _coordinator(hass, mock_entry)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_auto_sync_default_on_triggers_sync(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """With no option set, a refresh syncs the clock on connect."""
    coordinator = _coordinator(hass, mock_entry)
    await coordinator.async_refresh()
    assert coordinator.sync_on_connect is True
    assert mock_client.sync_time.await_count == 1


async def test_auto_sync_off_skips_sync(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """With the option off, a refresh does not sync on connect."""
    entry = MockConfigEntry(
        domain="qingping_cgd1",
        unique_id=MAC,
        data={"address": MAC, "token": "6e021111c28d192cfedbe04038a7f238"},
        options={CONF_SYNC_TIME_ON_CONNECT: False},
    )
    coordinator = _coordinator(hass, entry)
    await coordinator.async_refresh()
    assert coordinator.sync_on_connect is False
    assert mock_client.sync_time.await_count == 0


async def test_write_auth_error_becomes_config_entry_auth_failed(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """An AuthError during a write maps to ConfigEntryAuthFailed, triggering reauth.

    The coordinator's _write() helper catches AuthError just like _async_update_data()
    does, ensuring all write paths (async_update_settings, async_write_alarm, etc.)
    properly signal reauth on token loss.
    """
    coordinator = _coordinator(hass, mock_entry)
    await coordinator.async_refresh()
    mock_client.write_settings.side_effect = AuthError("clock is bound elsewhere")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_update_settings(volume=5)


@freeze_time("2026-07-01 12:00:00")
async def test_tz_mismatch_corrects_offset(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A DST mismatch writes the corrected offset and returns it in data."""
    await hass.config.async_set_time_zone("Pacific/Auckland")  # NZST here: +12:00
    coordinator = _coordinator(hass, mock_entry)
    await coordinator.async_refresh()

    written = mock_client.write_settings.await_args.args[0]
    assert written.tz_offset_minutes == 720
    assert coordinator.data.settings.tz_offset_minutes == 720


@freeze_time("2026-01-15 12:00:00")
async def test_tz_match_skips_write(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """No write happens when the stored offset already matches HA's."""
    await hass.config.async_set_time_zone("Pacific/Auckland")  # NZDT here: +13:00
    coordinator = _coordinator(hass, mock_entry)
    await coordinator.async_refresh()

    assert mock_client.write_settings.await_count == 0
    assert (
        coordinator.data.settings.tz_offset_minutes
        == sample_settings().tz_offset_minutes
    )


@freeze_time("2026-07-01 12:00:00")
async def test_tz_matching_off_skips_write(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """With timezone matching off, a mismatch is left uncorrected."""
    await hass.config.async_set_time_zone("Pacific/Auckland")  # NZST here: +12:00
    entry = MockConfigEntry(
        domain="qingping_cgd1",
        unique_id=MAC,
        data={"address": MAC, "token": "6e021111c28d192cfedbe04038a7f238"},
        options={CONF_MATCH_HA_TIMEZONE: False},
    )
    coordinator = _coordinator(hass, entry)
    await coordinator.async_refresh()

    assert mock_client.write_settings.await_count == 0
    assert (
        coordinator.data.settings.tz_offset_minutes
        == sample_settings().tz_offset_minutes
    )


def test_update_interval_reflects_option(hass: HomeAssistant) -> None:
    """The configured sync interval becomes the coordinator's update_interval."""
    twelve_hourly = MockConfigEntry(
        domain="qingping_cgd1",
        unique_id=f"{MAC}-12h",
        data={"address": MAC, "token": "6e021111c28d192cfedbe04038a7f238"},
        options={CONF_SYNC_INTERVAL_HOURS: 12},
    )
    assert _coordinator(hass, twelve_hourly).update_interval == timedelta(hours=12)

    disabled = MockConfigEntry(
        domain="qingping_cgd1",
        unique_id=f"{MAC}-disabled",
        data={"address": MAC, "token": "6e021111c28d192cfedbe04038a7f238"},
        options={CONF_SYNC_INTERVAL_HOURS: 0},
    )
    assert _coordinator(hass, disabled).update_interval is None
