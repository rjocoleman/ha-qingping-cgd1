"""Update coordinator for the Qingping CGD1 (placeholder).

The polling/control coordinator itself lands in a later task. This module
exists so the shared `mock_client` test fixture, which patches the BLE
client and lookup a coordinator will use, has something to patch.
"""

from __future__ import annotations

from homeassistant.components.bluetooth import async_ble_device_from_address

from qingping_cgd1.client import QingpingCGD1Client

__all__ = ["QingpingCGD1Client", "async_ble_device_from_address"]
