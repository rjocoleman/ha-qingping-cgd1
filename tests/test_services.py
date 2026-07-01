"""Service call tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_ADDRESS
from homeassistant.exceptions import ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from qingping_cgd1.models import Weekday
import voluptuous as vol

from custom_components.qingping_cgd1.const import (
    ATTR_DAYS,
    ATTR_SLOT,
    ATTR_SNOOZE,
    ATTR_TIME,
    CONF_SYNC_TIME_ON_CONNECT,
    CONF_TOKEN,
    DOMAIN,
    SERVICE_DELETE_ALARM,
    SERVICE_SET_ALARM,
    SERVICE_SYNC_TIME,
)
from qingping_cgd1.const import DEFAULT_AUTH_TOKEN
from tests.conftest import MAC

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant


async def _device_id(hass: HomeAssistant) -> str:
    registry = hass.data["device_registry"]
    device = registry.async_get_device(connections={("bluetooth", MAC)})
    assert device is not None
    return device.id


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_set_alarm_builds_days_bitmask(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """set_alarm builds an Alarm with the weekday set and writes the slot."""
    await _setup(hass, mock_entry)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ALARM,
        {
            "device_id": await _device_id(hass),
            ATTR_SLOT: 2,
            ATTR_TIME: "06:45:00",
            ATTR_DAYS: ["monday", "saturday"],
            ATTR_SNOOZE: True,
        },
        blocking=True,
    )
    slot, alarm = mock_client.write_alarm.await_args.args
    assert slot == 2
    assert alarm.hour == 6
    assert alarm.minute == 45
    assert alarm.days == frozenset({Weekday.MONDAY, Weekday.SATURDAY})
    assert alarm.snooze is True
    assert alarm.enabled is True


async def test_set_alarm_via_target_device_list(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A target-selected device_id arrives as a list, matching HA's target normalisation."""
    await _setup(hass, mock_entry)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ALARM,
        {
            "device_id": [await _device_id(hass)],
            ATTR_SLOT: 3,
            ATTR_TIME: "07:15:00",
            ATTR_DAYS: ["sunday"],
        },
        blocking=True,
    )
    slot, alarm = mock_client.write_alarm.await_args.args
    assert slot == 3
    assert alarm.hour == 7
    assert alarm.minute == 15
    assert alarm.days == frozenset({Weekday.SUNDAY})


async def test_delete_alarm(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """delete_alarm clears the given slot."""
    await _setup(hass, mock_entry)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_ALARM,
        {"device_id": await _device_id(hass), ATTR_SLOT: 4},
        blocking=True,
    )
    assert mock_client.delete_alarm.await_args.args[0] == 4


async def test_delete_alarm_rejects_out_of_range_slot(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A slot outside 0-15 fails schema validation."""
    await _setup(hass, mock_entry)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_ALARM,
            {"device_id": await _device_id(hass), ATTR_SLOT: 16},
            blocking=True,
        )
    mock_client.delete_alarm.assert_not_awaited()


async def test_set_alarm_rejects_unknown_device(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """An unrecognised device target raises a validation error."""
    await _setup(hass, mock_entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_ALARM,
            {
                "device_id": "not-a-real-device",
                ATTR_SLOT: 0,
                ATTR_TIME: "06:00:00",
            },
            blocking=True,
        )
    mock_client.write_alarm.assert_not_awaited()


async def test_set_alarm_rejects_not_loaded_entry(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A device whose config entry is not loaded raises, not AttributeError."""
    await _setup(hass, mock_entry)
    device_id = await _device_id(hass)
    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_ALARM,
            {"device_id": device_id, ATTR_SLOT: 0, ATTR_TIME: "06:00:00"},
            blocking=True,
        )
    mock_client.write_alarm.assert_not_awaited()


async def test_sync_time_service(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_client: MagicMock,
) -> None:
    """sync_time syncs the clock."""
    # sync-on-connect disabled so setup doesn't also sync the clock, which
    # would make the call count below ambiguous.
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_ADDRESS: MAC, CONF_TOKEN: DEFAULT_AUTH_TOKEN.hex()},
        options={CONF_SYNC_TIME_ON_CONNECT: False},
    )
    await _setup(hass, entry)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SYNC_TIME,
        {"device_id": await _device_id(hass)},
        blocking=True,
    )
    assert mock_client.sync_time.await_count == 1
