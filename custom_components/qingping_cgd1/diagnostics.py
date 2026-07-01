"""Diagnostics for the Qingping CGD1 (auth token redacted)."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CONF_TOKEN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import QingpingConfigEntry

TO_REDACT = {CONF_TOKEN}


def _serialise(value: Any) -> Any:
    """Make library dataclasses and bytes JSON-friendly."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _serialise(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, (list, frozenset, set, tuple)):
        return [_serialise(item) for item in value]
    if isinstance(value, bytes):
        return value.hex()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):  # IntEnum / StrEnum members
        return value.value
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: QingpingConfigEntry
) -> dict[str, Any]:
    """Return a redacted diagnostics dump."""
    control = entry.runtime_data.control
    data = control.data
    # `data` is typed non-optional but is really `None` until the first
    # refresh completes, same caveat as `QingpingControlCoordinator.device_info`.
    if data is not None:
        control_diagnostics: dict[str, Any] = {
            "settings": _serialise(data.settings),
            "alarms": _serialise(data.alarms),
            "firmware": data.firmware,
        }
    else:
        control_diagnostics = {  # type: ignore[unreachable]
            "settings": None,
            "alarms": [],
            "firmware": None,
        }
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "control": control_diagnostics,
    }
