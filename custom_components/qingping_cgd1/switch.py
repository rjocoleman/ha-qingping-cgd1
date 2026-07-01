"""Switches for the master alarm toggle, night mode and per-alarm enable."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory

from qingping_cgd1.const import ALARM_SLOT_COUNT

from .const import DEFAULT_ENABLED_ALARM_SLOTS
from .entity import PARALLEL_UPDATES, QingpingControlEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import QingpingConfigEntry, QingpingControlCoordinator

__all__ = ["PARALLEL_UPDATES"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QingpingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the settings switches plus one enable switch per alarm slot."""
    coordinator = entry.runtime_data.control
    entities: list[SwitchEntity] = [
        QingpingMasterSwitch(coordinator),
        QingpingNightModeSwitch(coordinator),
    ]
    entities.extend(
        QingpingAlarmEnableSwitch(coordinator, slot) for slot in range(ALARM_SLOT_COUNT)
    )
    async_add_entities(entities)


class QingpingMasterSwitch(QingpingControlEntity, SwitchEntity):
    """The master alarm enable."""

    def __init__(self, coordinator: QingpingControlCoordinator) -> None:
        """Bind to alarms_enabled."""
        super().__init__(coordinator, "alarms")
        self.entity_description = SwitchEntityDescription(
            key="alarms", translation_key="alarms"
        )

    @property
    def is_on(self) -> bool | None:
        """Whether alarms are enabled overall."""
        if self.coordinator.data is None:
            return None  # type: ignore[unreachable]
        return self.coordinator.data.settings.alarms_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable all alarms."""
        await self.coordinator.async_update_settings(alarms_enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable all alarms."""
        await self.coordinator.async_update_settings(alarms_enabled=False)


class QingpingNightModeSwitch(QingpingControlEntity, SwitchEntity):
    """Night mode."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: QingpingControlCoordinator) -> None:
        """Bind to night_mode."""
        super().__init__(coordinator, "night_mode")
        self.entity_description = SwitchEntityDescription(
            key="night_mode", translation_key="night_mode"
        )

    @property
    def is_on(self) -> bool | None:
        """Whether night mode is on."""
        if self.coordinator.data is None:
            return None  # type: ignore[unreachable]
        return self.coordinator.data.settings.night_mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable night mode."""
        await self.coordinator.async_update_settings(night_mode=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable night mode."""
        await self.coordinator.async_update_settings(night_mode=False)


class QingpingAlarmEnableSwitch(QingpingControlEntity, SwitchEntity):
    """Enable or disable a single alarm slot."""

    def __init__(self, coordinator: QingpingControlCoordinator, slot: int) -> None:
        """Bind to one alarm slot; hide slots past the first few by default."""
        # The unique id encodes the slot; all 16 share one translation with a
        # {slot} placeholder so there is a single display-name string.
        super().__init__(coordinator, f"alarm_{slot + 1}_enabled")
        self._slot = slot
        self._attr_translation_key = "alarm_enabled"
        self._attr_translation_placeholders = {"slot": str(slot + 1)}
        self._attr_entity_registry_enabled_default = slot < DEFAULT_ENABLED_ALARM_SLOTS

    @property
    def is_on(self) -> bool | None:
        """Whether this alarm is enabled."""
        if self.coordinator.data is None:
            return None  # type: ignore[unreachable]
        return self.coordinator.data.alarms[self._slot].enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable this alarm."""
        await self._set_enabled(enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable this alarm."""
        await self._set_enabled(enabled=False)

    async def _set_enabled(self, *, enabled: bool) -> None:
        if self.coordinator.data is None:
            return  # type: ignore[unreachable]
        alarm = self.coordinator.data.alarms[self._slot]
        await self.coordinator.async_write_alarm(
            self._slot, dataclasses.replace(alarm, enabled=enabled)
        )
