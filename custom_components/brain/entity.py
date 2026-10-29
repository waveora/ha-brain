"""Base entity: one HA device per Brain device, updated by the device's listeners."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .device import BrainDevice


class BrainEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: BrainDevice, model: str, key: str) -> None:
        self.device = device
        self._attr_unique_id = f"{device.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            manufacturer=MANUFACTURER,
            model=model,
            name=f"{model} {device.device_id[-4:]}",
            sw_version=device.version,
            configuration_url=device.api.base,
        )

    @property
    def available(self) -> bool:
        return self.device.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.device.add_listener(self.async_write_ha_state))
