"""Diagnostics redaction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.qingping_cgd1.diagnostics import (
    async_get_config_entry_diagnostics,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_diagnostics_redacts_token(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """The token is redacted; settings and alarms survive."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_entry)

    assert diagnostics["entry"]["token"] == "**REDACTED**"  # noqa: S105 -- expected value, not a secret
    assert diagnostics["control"]["settings"]["volume"] == 3
    assert diagnostics["control"]["firmware"] == "1.2.3"
    assert len(diagnostics["control"]["alarms"]) == 16
