"""Sensors: passive climate/battery/signal plus a firmware diagnostic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from qingping_cgd1.codec import next_alarm, parse_advertisement

from .const import DEFAULT_NAME, MANUFACTURER, MODEL, SERVICE_DATA_UUID

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import QingpingConfigEntry, QingpingControlCoordinator

# The passive coordinator dispatches; entities never poll.
PARALLEL_UPDATES = 0

_TEMPERATURE = PassiveBluetoothEntityKey("temperature", None)
_HUMIDITY = PassiveBluetoothEntityKey("humidity", None)
_BATTERY = PassiveBluetoothEntityKey("battery", None)
_SIGNAL = PassiveBluetoothEntityKey("signal_strength", None)

_DESCRIPTIONS: dict[PassiveBluetoothEntityKey, SensorEntityDescription] = {
    _TEMPERATURE: SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _HUMIDITY: SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # The library's advertisement battery value is a raw 0-255 passthrough with
    # no clamping. The device only ever emits 0-100, so no clamping is added
    # here - a conscious choice, not an oversight.
    _BATTERY: SensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _SIGNAL: SensorEntityDescription(
        key="signal_strength",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


def _sensor_update(
    service_info: BluetoothServiceInfoBleak,
) -> PassiveBluetoothDataUpdate[float | int | None]:
    """Turn one advertisement into the sensor data update."""
    raw = service_info.service_data.get(SERVICE_DATA_UUID)
    parsed = parse_advertisement(raw) if raw else None
    device = DeviceInfo(
        connections={(CONNECTION_BLUETOOTH, service_info.address)},
        name=DEFAULT_NAME,
        manufacturer=MANUFACTURER,
        model=MODEL,
    )
    values: dict[PassiveBluetoothEntityKey, float | int | None] = {
        _SIGNAL: service_info.rssi,
    }
    if parsed is not None:
        values[_TEMPERATURE] = parsed.temperature
        values[_HUMIDITY] = parsed.humidity
        values[_BATTERY] = parsed.battery

    present: dict[PassiveBluetoothEntityKey, float | int | None] = {
        key: value for key, value in values.items() if value is not None
    }
    return PassiveBluetoothDataUpdate(
        devices={None: device},
        entity_descriptions={key: _DESCRIPTIONS[key] for key in present},
        entity_data=present,
        entity_names=dict.fromkeys(present),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QingpingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Register the passive processor and add the connection-backed sensors."""
    data = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(_sensor_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            QingpingBluetoothSensor, async_add_entities
        )
    )
    entry.async_on_unload(
        data.passive.async_register_processor(processor, SensorEntityDescription)
    )
    async_add_entities(
        [
            QingpingFirmwareSensor(data.control),
            QingpingNextAlarmSensor(data.control),
        ]
    )


class QingpingBluetoothSensor(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[float | int | None, BluetoothServiceInfoBleak]
    ],
    SensorEntity,
):
    """A sensor fed by the passive advertisement processor."""

    @property
    def native_value(self) -> float | int | None:
        """The latest value for this entity key."""
        return self.processor.entity_data.get(self.entity_key)


class QingpingFirmwareSensor(
    CoordinatorEntity["QingpingControlCoordinator"], SensorEntity
):
    """The device firmware version, read over the control connection."""

    _attr_has_entity_name = True
    _attr_translation_key = "firmware"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: QingpingControlCoordinator) -> None:
        """Bind the firmware sensor to the control coordinator."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_firmware"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> str | None:
        """The firmware string, or None before the first read."""
        if self.coordinator.data is None:
            return None  # type: ignore[unreachable]
        return self.coordinator.data.firmware


class QingpingNextAlarmSensor(
    CoordinatorEntity["QingpingControlCoordinator"], SensorEntity
):
    """The next time any enabled alarm will fire."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_alarm"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: QingpingControlCoordinator) -> None:
        """Bind the next-alarm sensor to the control coordinator."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_next_alarm"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> datetime | None:
        """The soonest alarm as an aware timestamp, or None if none are set.

        The clock keeps wall-clock time in its own timezone, so the library
        computation must run against a `now` in that same offset.
        """
        data = self.coordinator.data
        if data is None:
            return None  # type: ignore[unreachable]
        device_tz = timezone(timedelta(minutes=data.settings.tz_offset_minutes))
        now = datetime.now(tz=device_tz)
        return next_alarm(data.alarms, now)
