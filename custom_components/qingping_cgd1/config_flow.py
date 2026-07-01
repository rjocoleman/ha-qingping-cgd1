"""Config flow for the Qingping CGD1 integration.

Placeholder registration only; the discovery and setup steps land in a
later task. HA's loader imports this module for any domain that declares
`config_flow: true` in its manifest, even when setting up a config entry
programmatically (as the init smoke test does), so a bare handler is
required from the outset.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class QingpingCGD1ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qingping CGD1."""

    VERSION = 1
