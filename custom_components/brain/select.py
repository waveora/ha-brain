"""Select: how many current transformers are fitted (septic `ct_count`)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
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
    # Control entities only with a token: an unpaired device takes anyone's.
    if data.device.api.token and "setup" in data.device.sections:
        async_add_entities([CtCountSelect(data.device, data.product.model, entry)])


class CtCountSelect(BrainEntity, SelectEntity):
    """Changing it restarts the device to apply it."""

    _attr_name = "Current sensors fitted"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = ["1", "2", "3"]

    def __init__(self, device: BrainDevice, model: str, entry: BrainConfigEntry) -> None:
        super().__init__(device, model, "ct_count_select")
        self._entry = entry

    @property
    def current_option(self) -> str | None:
        count = (self.device.sections.get("setup") or {}).get("ct_count")
        return None if count is None else str(count)

    async def async_select_option(self, option: str) -> None:
        await send_action(self.device, self._entry, f"ct_count/{option}")
