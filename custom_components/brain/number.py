"""Number: the relay interlock's maximum continuous on-time (septic)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BrainConfigEntry
from .control import send_action
from .device import BrainDevice
from .entity import BrainEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: BrainConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    data = entry.runtime_data
    relay = data.device.sections.get("relay") or {}
    if data.device.api.token and "max_on_s" in relay:
        async_add_entities([RelayMaxOnNumber(data.device, data.product.model, entry)])


class RelayMaxOnNumber(BrainEntity, NumberEntity):
    """The device turns the relay off after this long on, whoever turned it on."""

    _attr_name = "Relay maximum on-time"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(self, device: BrainDevice, model: str, entry: BrainConfigEntry) -> None:
        super().__init__(device, model, "relay_max_on")
        self._entry = entry

    @property
    def native_value(self) -> float | None:
        max_on_s = (self.device.sections.get("relay") or {}).get("max_on_s")
        return None if max_on_s is None else round(max_on_s / 60)

    async def async_set_native_value(self, value: float) -> None:
        await send_action(self.device, self._entry, f"relay/max_on/{int(value)}")
