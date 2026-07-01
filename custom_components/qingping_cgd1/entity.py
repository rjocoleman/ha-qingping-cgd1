"""Shared base for the connection-backed control entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from .coordinator import QingpingControlCoordinator

# One coordinator owns the connection; entities never talk to the device in
# parallel.
PARALLEL_UPDATES = 1


class QingpingControlEntity(CoordinatorEntity["QingpingControlCoordinator"]):
    """A control entity bound to the shared connection coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: QingpingControlCoordinator, key: str) -> None:
        """Wire the entity to the coordinator, device and a translation key."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = coordinator.device_info
