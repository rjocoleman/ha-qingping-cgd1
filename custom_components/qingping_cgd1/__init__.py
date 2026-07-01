"""Qingping CGD1 alarm clock integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .coordinator import (
    QingpingControlCoordinator,
    QingpingData,
    QingpingPassiveCoordinator,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import QingpingConfigEntry

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: QingpingConfigEntry) -> bool:
    """Set up a Qingping CGD1 device from a config entry."""
    passive = QingpingPassiveCoordinator(hass, entry)
    control = QingpingControlCoordinator(hass, entry)
    entry.runtime_data = QingpingData(passive=passive, control=control)

    entry.async_on_unload(passive.async_start())
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Populate the control entities without blocking setup: a push integration
    # must not fail to load just because the clock is momentarily out of range.
    await control.async_refresh()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: QingpingConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_on_update(
    hass: HomeAssistant, entry: QingpingConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
