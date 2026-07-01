"""Setup and unload for the Qingping CGD1 integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_manifest_domain(hass: HomeAssistant) -> None:
    """The integration constant matches the manifest domain."""
    from custom_components.qingping_cgd1.const import DOMAIN  # noqa: PLC0415

    assert DOMAIN == "qingping_cgd1"


async def test_setup_and_unload(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A configured entry loads and unloads cleanly."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_runtime_data_is_populated(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: object
) -> None:
    """Setup stores both coordinators on the entry."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    data = mock_entry.runtime_data
    assert data.passive is not None
    assert data.control is not None
