"""Switch: the septic pump relay, only when the user opted in (off by default)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BrainConfigEntry
from .const import OPT_RELAY_CONTROL
from .control import send_action
from .device import BrainDevice
from .entity import BrainEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: BrainConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    data = entry.runtime_data
    if data.device.api.token and "relay" in data.device.sections and entry.options.get(OPT_RELAY_CONTROL, False):
        async_add_entities([RelaySwitch(data.device, data.product.model, entry)])


class RelaySwitch(BrainEntity, SwitchEntity):
    """On/off follows what the device applied, not the last command."""

    _attr_name = "Pump relay control"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:pump"

    def __init__(self, device: BrainDevice, model: str, entry: BrainConfigEntry) -> None:
        super().__init__(device, model, "relay_switch")
        self._entry = entry

    @property
    def is_on(self) -> bool | None:
        return (self.device.sections.get("relay") or {}).get("on")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await send_action(self.device, self._entry, "relay/on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await send_action(self.device, self._entry, "relay/off")
