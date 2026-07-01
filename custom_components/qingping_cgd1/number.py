"""Number controls backed by the device settings blob."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime

from .entity import PARALLEL_UPDATES, QingpingControlEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from qingping_cgd1.models import DeviceSettings

    from .coordinator import QingpingConfigEntry, QingpingControlCoordinator

__all__ = ["PARALLEL_UPDATES"]


@dataclass(frozen=True, kw_only=True)
class QingpingNumberDescription(NumberEntityDescription):
    """A number bound to one settings field."""

    value_fn: Callable[[DeviceSettings], int]
    setting_key: str


_NUMBERS: tuple[QingpingNumberDescription, ...] = (
    QingpingNumberDescription(
        key="volume",
        translation_key="volume",
        native_min_value=1,
        native_max_value=5,
        native_step=1,
        value_fn=lambda settings: settings.volume,
        setting_key="volume",
    ),
    QingpingNumberDescription(
        key="day_brightness",
        translation_key="day_brightness",
        native_min_value=0,
        native_max_value=100,
        native_step=10,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda settings: settings.day_brightness,
        setting_key="day_brightness",
    ),
    QingpingNumberDescription(
        key="night_brightness",
        translation_key="night_brightness",
        native_min_value=0,
        native_max_value=100,
        native_step=10,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda settings: settings.night_brightness,
        setting_key="night_brightness",
    ),
    QingpingNumberDescription(
        key="screen_light_seconds",
        translation_key="screen_light_seconds",
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda settings: settings.screen_light_seconds,
        setting_key="screen_light_seconds",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QingpingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the settings-backed numbers."""
    coordinator = entry.runtime_data.control
    async_add_entities(
        QingpingNumber(coordinator, description) for description in _NUMBERS
    )


class QingpingNumber(QingpingControlEntity, NumberEntity):
    """A single settings field exposed as a number."""

    entity_description: QingpingNumberDescription

    def __init__(
        self,
        coordinator: QingpingControlCoordinator,
        description: QingpingNumberDescription,
    ) -> None:
        """Bind the number to a settings field."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """The current field value, or None before the first read."""
        if self.coordinator.data is None:
            return None  # type: ignore[unreachable]
        return float(self.entity_description.value_fn(self.coordinator.data.settings))

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value into the settings blob."""
        await self.coordinator.async_update_settings(
            **{self.entity_description.setting_key: int(value)}
        )
