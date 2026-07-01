"""Constants for the Qingping CGD1 integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "qingping_cgd1"

# fdcd carries the passive sensor advertisement; the vendor 128-bit service uuid
# is the other reliable discovery signal. Both are stored as full HA uuids.
SERVICE_DATA_UUID: Final = "0000fdcd-0000-1000-8000-00805f9b34fb"
DEVICE_SERVICE_UUID: Final = "22210000-554a-4546-5542-46534450464d"

CONF_TOKEN: Final = "token"  # noqa: S105 -- config key name, not a secret value
# Sync the clock on every successful control connect. Default on; toggled in the
# options flow.
CONF_SYNC_TIME_ON_CONNECT: Final = "sync_time_on_connect"
DEFAULT_SYNC_TIME_ON_CONNECT: Final = True
# Correct the clock's stored tz offset to Home Assistant's current (DST-aware)
# offset whenever they differ. Default on; toggled in the options flow.
CONF_MATCH_HA_TIMEZONE: Final = "match_ha_timezone"
DEFAULT_MATCH_HA_TIMEZONE: Final = True
# How often the control coordinator polls to correct drift and the tz offset.
# 0 disables periodic polling; the coordinator still refreshes on demand.
CONF_SYNC_INTERVAL_HOURS: Final = "sync_interval_hours"
DEFAULT_SYNC_INTERVAL_HOURS: Final = 24

DEFAULT_NAME: Final = "Qingping Alarm Clock"
MANUFACTURER: Final = "Qingping"
MODEL: Final = "CGD1"

# Slots 0 and 1 are visible out of the box; the rest stay disabled so someone
# with two alarms is not buried under 32 entities.
DEFAULT_ENABLED_ALARM_SLOTS: Final = 2

SERVICE_SET_ALARM: Final = "set_alarm"
SERVICE_DELETE_ALARM: Final = "delete_alarm"
SERVICE_SYNC_TIME: Final = "sync_time"

ATTR_SLOT: Final = "slot"
ATTR_DAYS: Final = "days"
ATTR_SNOOZE: Final = "snooze"
ATTR_ENABLED: Final = "enabled"
ATTR_TIME: Final = "time"
