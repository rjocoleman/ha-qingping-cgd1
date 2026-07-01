"""Config-flow tests: bluetooth discovery and manual selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType
from qingping_cgd1.exceptions import AuthError

from custom_components.qingping_cgd1.const import CONF_TOKEN, DOMAIN
from qingping_cgd1.const import DEFAULT_AUTH_TOKEN
from tests.conftest import MAC, inject_service_info, make_service_info

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

TOKEN_HEX = DEFAULT_AUTH_TOKEN.hex()


async def test_bluetooth_discovery_creates_entry(
    hass: HomeAssistant, enable_bluetooth: None, mock_client: MagicMock
) -> None:
    """A discovered device confirms with the default token and is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: TOKEN_HEX}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MAC
    assert result["data"] == {CONF_ADDRESS: MAC, CONF_TOKEN: TOKEN_HEX}
    assert mock_client.connect.await_count == 1


async def test_bluetooth_discovery_rejects_bad_token(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """A token that is not 16 bytes of hex reshows the confirm form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "not-hex"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_TOKEN: "invalid_token"}


async def test_bluetooth_discovery_needs_reset_on_auth_error(
    hass: HomeAssistant, enable_bluetooth: None, mock_client: MagicMock
) -> None:
    """A clock already bound to another token (e.g. the Qingping+ app) needs a reset.

    Hardware confirmed the token is a per-device pairing secret, not a
    universal key: an already-paired clock rejects our default token and
    `connect()` raises `AuthError`.
    """
    mock_client.connect.side_effect = AuthError("already bound")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: TOKEN_HEX}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "needs_reset"}


async def test_manual_user_flow(
    hass: HomeAssistant, enable_bluetooth: None, mock_client: MagicMock
) -> None:
    """The user step lists a discovered device and creates its entry."""
    inject_service_info(hass, make_service_info())
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: MAC, CONF_TOKEN: TOKEN_HEX}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MAC


async def test_user_flow_no_devices_aborts(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """With nothing discovered the user step aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_discovery_of_configured_device_aborts(
    hass: HomeAssistant, enable_bluetooth: None, mock_entry: MockConfigEntry
) -> None:
    """A rediscovery of an already-configured MAC aborts."""
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Reauth retries the connection and stores the (possibly new) token."""
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: TOKEN_HEX}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data[CONF_TOKEN] == TOKEN_HEX


async def test_reauth_flow_needs_reset(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A clock that is still bound to another token keeps failing reauth."""
    mock_entry.add_to_hass(hass)
    mock_client.connect.side_effect = AuthError("already bound")
    result = await mock_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: TOKEN_HEX}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "needs_reset"}
