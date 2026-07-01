"""Time controls for the night window and per-alarm times."""

from __future__ import annotations

import dataclasses
from datetime import time as time_cls
from typing import TYPE_CHECKING, cast

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory

from qingping_cgd1.const import ALARM_SLOT_COUNT

from .const import DEFAULT_ENABLED_ALARM_SLOTS
from .entity import PARALLEL_UPDATES, QingpingControlEntity

if TYPE_CHECKING:
    from datetime import time

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import QingpingConfigEntry, QingpingControlCoordinator

__all__ = ["PARALLEL_UPDATES"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QingpingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the night-window times and one time per alarm slot."""
    coordinator = entry.runtime_data.control
    entities: list[TimeEntity] = [
        QingpingNightWindowTime(coordinator, "night_start"),
        QingpingNightWindowTime(coordinator, "night_end"),
    ]
    entities.extend(
        QingpingAlarmTime(coordinator, slot) for slot in range(ALARM_SLOT_COUNT)
    )
    async_add_entities(entities)


class QingpingNightWindowTime(QingpingControlEntity, TimeEntity):
    """One end of the night window, backed by a settings field."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: QingpingControlCoordinator, field: str) -> None:
        """Bind to night_start or night_end."""
        super().__init__(coordinator, field)
        self._field = field
        self.entity_description = TimeEntityDescription(
            key=field, translation_key=field
        )

    @property
    def native_value(self) -> time | None:
        """The current night-window boundary."""
        if self.coordinator.data is None:
            return None  # type: ignore[unreachable]
        return cast("time", getattr(self.coordinator.data.settings, self._field))

    async def async_set_value(self, value: time) -> None:
        """Write the new boundary into settings."""
        await self.coordinator.async_update_settings(**{self._field: value})


class QingpingAlarmTime(QingpingControlEntity, TimeEntity):
    """The time of a single alarm slot."""

    def __init__(self, coordinator: QingpingControlCoordinator, slot: int) -> None:
        """Bind to one alarm slot; hide slots past the first few by default."""
        super().__init__(coordinator, f"alarm_{slot + 1}_time")
        self._slot = slot
        self._attr_translation_key = "alarm_time"
        self._attr_translation_placeholders = {"slot": str(slot + 1)}
        self._attr_entity_registry_enabled_default = slot < DEFAULT_ENABLED_ALARM_SLOTS

    @property
    def native_value(self) -> time | None:
        """The alarm time, or None for an empty slot."""
        if self.coordinator.data is None:
            return None  # type: ignore[unreachable]
        alarm = self.coordinator.data.alarms[self._slot]
        if alarm.is_empty:
            return None
        return time_cls(hour=alarm.hour, minute=alarm.minute)

    async def async_set_value(self, value: time) -> None:
        """Write the new alarm time, keeping the other fields intact."""
        if self.coordinator.data is None:
            return  # type: ignore[unreachable]
        alarm = self.coordinator.data.alarms[self._slot]
        await self.coordinator.async_write_alarm(
            self._slot,
            dataclasses.replace(alarm, hour=value.hour, minute=value.minute),
        )
