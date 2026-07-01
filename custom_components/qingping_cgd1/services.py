"""Domain services for alarms and time sync."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
import voluptuous as vol

from qingping_cgd1.const import ALARM_SLOT_COUNT
from qingping_cgd1.models import Alarm, Weekday

from .const import (
    ATTR_DAYS,
    ATTR_ENABLED,
    ATTR_SLOT,
    ATTR_SNOOZE,
    ATTR_TIME,
    DOMAIN,
    SERVICE_DELETE_ALARM,
    SERVICE_SET_ALARM,
    SERVICE_SYNC_TIME,
)

if TYPE_CHECKING:
    from datetime import time

    from .coordinator import QingpingConfigEntry, QingpingControlCoordinator

_WEEKDAYS = {name.lower(): member for name, member in Weekday.__members__.items()}

_SLOT = vol.All(vol.Coerce(int), vol.Range(min=0, max=ALARM_SLOT_COUNT - 1))

# HA's target selector always normalises device_id to a list (via
# ensure_list), even for a single device, so the schema must accept a list.
# cv.ensure_list also wraps a bare string, so direct calls still work too.
_DEVICE_IDS = vol.All(cv.ensure_list, [cv.string])

_SET_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): _DEVICE_IDS,
        vol.Required(ATTR_SLOT): _SLOT,
        vol.Required(ATTR_TIME): cv.time,
        vol.Optional(ATTR_DAYS, default=list): vol.All(
            cv.ensure_list, [vol.In(_WEEKDAYS)]
        ),
        vol.Optional(ATTR_SNOOZE, default=False): cv.boolean,
        vol.Optional(ATTR_ENABLED, default=True): cv.boolean,
    }
)

_DELETE_ALARM_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): _DEVICE_IDS, vol.Required(ATTR_SLOT): _SLOT}
)

_SYNC_TIME_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): _DEVICE_IDS})


def _coordinator(hass: HomeAssistant, device_id: str) -> QingpingControlCoordinator:
    """Resolve a device target to its loaded control coordinator."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        msg = f"Unknown device {device_id}"
        raise ServiceValidationError(msg)
    for entry_id in device.config_entries:
        entry: QingpingConfigEntry | None = hass.config_entries.async_get_entry(
            entry_id
        )
        if entry is not None and entry.domain == DOMAIN:
            if entry.state is not ConfigEntryState.LOADED:
                msg = (
                    f"The Qingping CGD1 integration entry for {device_id} is not loaded"
                )
                raise ServiceValidationError(msg)
            return entry.runtime_data.control
    msg = f"Device {device_id} is not a loaded Qingping CGD1"
    raise ServiceValidationError(msg)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the domain services once."""

    async def _set_alarm(call: ServiceCall) -> None:
        moment: time = call.data[ATTR_TIME]
        days = frozenset(_WEEKDAYS[name] for name in call.data[ATTR_DAYS])
        alarm = Alarm(
            enabled=call.data[ATTR_ENABLED],
            hour=moment.hour,
            minute=moment.minute,
            days=days,
            snooze=call.data[ATTR_SNOOZE],
        )
        for device_id in call.data[ATTR_DEVICE_ID]:
            coordinator = _coordinator(hass, device_id)
            await coordinator.async_write_alarm(call.data[ATTR_SLOT], alarm)

    async def _delete_alarm(call: ServiceCall) -> None:
        for device_id in call.data[ATTR_DEVICE_ID]:
            coordinator = _coordinator(hass, device_id)
            await coordinator.async_delete_alarm(call.data[ATTR_SLOT])

    async def _sync_time(call: ServiceCall) -> None:
        for device_id in call.data[ATTR_DEVICE_ID]:
            coordinator = _coordinator(hass, device_id)
            await coordinator.async_sync_time()

    hass.services.async_register(
        DOMAIN, SERVICE_SET_ALARM, _set_alarm, schema=_SET_ALARM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_ALARM, _delete_alarm, schema=_DELETE_ALARM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SYNC_TIME, _sync_time, schema=_SYNC_TIME_SCHEMA
    )
