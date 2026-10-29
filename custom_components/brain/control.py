"""Sending control actions: the token, and reauth when the device rejects it."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

from .api import BrainError, InvalidAuth
from .device import BrainDevice


async def send_action(device: BrainDevice, entry, name: str) -> None:
    """`POST /api/action/<name>`; a rejected token starts reauthentication."""
    try:
        await device.api.action(name)
    except InvalidAuth as err:
        entry.async_start_reauth(device.hass)
        raise HomeAssistantError("The device rejected the control token; re-enter it") from err
    except BrainError as err:
        raise HomeAssistantError(f"Device refused {name}: {err}") from err
