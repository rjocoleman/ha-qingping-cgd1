"""Config flow for the Qingping CGD1 alarm clock."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
import voluptuous as vol

from qingping_cgd1.client import QingpingCGD1Client
from qingping_cgd1.exceptions import AuthError, QingpingError

from .const import (
    CONF_MATCH_HA_TIMEZONE,
    CONF_SYNC_INTERVAL_HOURS,
    CONF_SYNC_TIME_ON_CONNECT,
    CONF_TOKEN,
    DEFAULT_MATCH_HA_TIMEZONE,
    DEFAULT_NAME,
    DEFAULT_SYNC_INTERVAL_HOURS,
    DEFAULT_SYNC_TIME_ON_CONNECT,
    DEVICE_SERVICE_UUID,
    DOMAIN,
    SERVICE_DATA_UUID,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
    from homeassistant.config_entries import ConfigEntry

TOKEN_LENGTH_BYTES = 16


def _is_cgd1(info: BluetoothServiceInfoBleak) -> bool:
    """Match a CGD1 by its fdcd service data or vendor service uuid."""
    return (
        SERVICE_DATA_UUID in info.service_data
        or DEVICE_SERVICE_UUID in info.service_uuids
    )


def _validate_token(token_hex: str) -> str | None:
    """Return an error key if the token is not 16 bytes of hex, else None."""
    try:
        token = bytes.fromhex(token_hex)
    except ValueError:
        return "invalid_token"
    return None if len(token) == TOKEN_LENGTH_BYTES else "invalid_token"


class QingpingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle discovery and manual setup of a CGD1."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with no pending discovery and a fresh suggested token.

        The token is a per-device pairing secret, not a shared default, so
        each new setup gets its own randomly generated token to bind.
        """
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._suggested_token = secrets.token_hex(TOKEN_LENGTH_BYTES)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> QingpingOptionsFlow:
        """Return the options flow."""
        return QingpingOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a device found by the bluetooth integration."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": DEFAULT_NAME}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device and take its auth token."""
        assert self._discovery is not None  # noqa: S101 -- narrows for mypy
        address = self._discovery.address
        errors: dict[str, str] = {}
        if user_input is not None:
            token_error = _validate_token(user_input[CONF_TOKEN])
            if token_error is not None:
                errors[CONF_TOKEN] = token_error
            else:
                connect_error = await self._async_try_connect(
                    address, user_input[CONF_TOKEN]
                )
                if connect_error is None:
                    return self._create(address, user_input[CONF_TOKEN])
                errors["base"] = connect_error
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=self._token_schema(self._suggested_token),
            errors=errors,
            description_placeholders={"name": DEFAULT_NAME, "address": address},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a discovered device and take its auth token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            token_error = _validate_token(user_input[CONF_TOKEN])
            if token_error is not None:
                errors[CONF_TOKEN] = token_error
            else:
                connect_error = await self._async_try_connect(
                    address, user_input[CONF_TOKEN]
                )
                if connect_error is None:
                    await self.async_set_unique_id(address, raise_on_progress=False)
                    self._abort_if_unique_id_configured()
                    return self._create(address, user_input[CONF_TOKEN])
                errors["base"] = connect_error

        configured = self._async_current_ids()
        choices = {
            info.address: f"{info.name} ({info.address})"
            for info in async_discovered_service_info(self.hass)
            if info.address not in configured and _is_cgd1(info)
        }
        if not choices:
            return self.async_abort(reason="no_devices_found")
        schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(choices),
                vol.Required(CONF_TOKEN, default=self._suggested_token): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth after the control coordinator hits an AuthError."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry the connection, prompting for a reset if it keeps failing."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token_error = _validate_token(user_input[CONF_TOKEN])
            if token_error is not None:
                errors[CONF_TOKEN] = token_error
            else:
                connect_error = await self._async_try_connect(
                    reauth_entry.data[CONF_ADDRESS], user_input[CONF_TOKEN]
                )
                if connect_error is None:
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data={
                            **reauth_entry.data,
                            CONF_TOKEN: user_input[CONF_TOKEN],
                        },
                    )
                errors["base"] = connect_error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._token_schema(reauth_entry.data[CONF_TOKEN]),
            errors=errors,
            description_placeholders={"name": DEFAULT_NAME},
        )

    async def _async_try_connect(self, address: str, token_hex: str) -> str | None:
        """Attempt to connect and authenticate; return an error key or None.

        A clock still bound to another token (e.g. the official Qingping+ app)
        answers the auth handshake with a failure status; the library raises
        `AuthError`. The clock must be unbound before it will accept our token.
        """
        device = async_ble_device_from_address(self.hass, address, connectable=True)
        if device is None:
            return "cannot_connect"
        client = QingpingCGD1Client(device, bytes.fromhex(token_hex))
        try:
            await client.connect()
        except AuthError:
            return "needs_reset"
        except QingpingError:
            return "cannot_connect"
        await client.disconnect()
        return None

    def _token_schema(self, default_hex: str) -> vol.Schema:
        return vol.Schema({vol.Required(CONF_TOKEN, default=default_hex): str})

    def _create(self, address: str, token_hex: str) -> ConfigFlowResult:
        return self.async_create_entry(
            title=DEFAULT_NAME,
            data={CONF_ADDRESS: address, CONF_TOKEN: token_hex},
        )


class QingpingOptionsFlow(OptionsFlow):
    """Toggle automatic time sync."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the auto-sync toggle."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current_sync_on_connect = self.config_entry.options.get(
            CONF_SYNC_TIME_ON_CONNECT, DEFAULT_SYNC_TIME_ON_CONNECT
        )
        current_match_ha_timezone = self.config_entry.options.get(
            CONF_MATCH_HA_TIMEZONE, DEFAULT_MATCH_HA_TIMEZONE
        )
        current_sync_interval_hours = self.config_entry.options.get(
            CONF_SYNC_INTERVAL_HOURS, DEFAULT_SYNC_INTERVAL_HOURS
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SYNC_TIME_ON_CONNECT, default=current_sync_on_connect
                ): bool,
                vol.Required(
                    CONF_MATCH_HA_TIMEZONE, default=current_match_ha_timezone
                ): bool,
                vol.Required(
                    CONF_SYNC_INTERVAL_HOURS, default=current_sync_interval_hours
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=168)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
