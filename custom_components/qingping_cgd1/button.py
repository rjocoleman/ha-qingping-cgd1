"""A button that pushes the current time to the clock."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription

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
    """Add the sync-time button."""
    async_add_entities([QingpingSyncTimeButton(entry.runtime_data.control)])


class QingpingSyncTimeButton(QingpingControlEntity, ButtonEntity):
    """Push the current time to the device."""

    def __init__(self, coordinator: QingpingControlCoordinator) -> None:
        """Bind the button to the coordinator."""
        super().__init__(coordinator, "sync_time")
        self.entity_description = ButtonEntityDescription(
            key="sync_time", translation_key="sync_time"
        )

    async def async_press(self) -> None:
        """Sync the clock."""
        await self.coordinator.async_sync_time()
