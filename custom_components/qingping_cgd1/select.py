"""Select controls for language, time format and temperature unit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory

from qingping_cgd1.models import Language

from .entity import PARALLEL_UPDATES, QingpingControlEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from qingping_cgd1.models import DeviceSettings

    from .coordinator import QingpingConfigEntry, QingpingControlCoordinator

__all__ = ["PARALLEL_UPDATES"]


@dataclass(frozen=True, kw_only=True)
class QingpingSelectDescription(SelectEntityDescription):
    """A select bound to one settings field."""

    value_fn: Callable[[DeviceSettings], str]
    setting_key: str
    parse_fn: Callable[[str], object]


_SELECTS: tuple[QingpingSelectDescription, ...] = (
    QingpingSelectDescription(
        key="language",
        translation_key="language",
        entity_category=EntityCategory.CONFIG,
        options=[Language.CHINESE.value, Language.ENGLISH.value],
        value_fn=lambda settings: settings.language.value,
        setting_key="language",
        parse_fn=Language,
    ),
    QingpingSelectDescription(
        key="time_format",
        translation_key="time_format",
        entity_category=EntityCategory.CONFIG,
        options=["24h", "12h"],
        value_fn=lambda settings: "24h" if settings.time_format_24h else "12h",
        setting_key="time_format_24h",
        parse_fn=lambda option: option == "24h",
    ),
    QingpingSelectDescription(
        key="temperature_unit",
        translation_key="temperature_unit",
        entity_category=EntityCategory.CONFIG,
        options=["celsius", "fahrenheit"],
        value_fn=lambda settings: "celsius" if settings.unit_celsius else "fahrenheit",
        setting_key="unit_celsius",
        parse_fn=lambda option: option == "celsius",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QingpingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the settings-backed selects."""
    coordinator = entry.runtime_data.control
    async_add_entities(
        QingpingSelect(coordinator, description) for description in _SELECTS
    )


class QingpingSelect(QingpingControlEntity, SelectEntity):
    """A single settings field exposed as a select."""

    entity_description: QingpingSelectDescription

    def __init__(
        self,
        coordinator: QingpingControlCoordinator,
        description: QingpingSelectDescription,
    ) -> None:
        """Bind the select to a settings field."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """The current field value, or None before the first read."""
        if self.coordinator.data is None:
            return None  # type: ignore[unreachable]
        return self.entity_description.value_fn(self.coordinator.data.settings)

    async def async_select_option(self, option: str) -> None:
        """Write the chosen option into the settings blob."""
        await self.coordinator.async_update_settings(
            **{
                self.entity_description.setting_key: self.entity_description.parse_fn(
                    option
                )
            }
        )
