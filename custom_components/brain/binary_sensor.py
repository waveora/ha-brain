"""Binary sensors: boolean catalog measurements."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BrainConfigEntry
from .catalog import Measurement, creates, enabled_default
from .device import BrainDevice
from .entity import BrainEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: BrainConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    data = entry.runtime_data
    async_add_entities(
        MeasurementBinarySensor(data.device, data.product.model, m)
        for m in data.product.measurements.values()
        if m.platform == "binary_sensor" and creates(m.name, data.device.sections)
    )


class MeasurementBinarySensor(BrainEntity, BinarySensorEntity):
    def __init__(self, device: BrainDevice, model: str, m: Measurement) -> None:
        super().__init__(device, model, m.name)
        self.m = m
        self._attr_name = m.label
        self._attr_entity_registry_enabled_default = enabled_default(m, device.sections)
        if m.ha.get("entity_category") == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if device_class := m.ha.get("device_class"):
            self._attr_device_class = BinarySensorDeviceClass(device_class)
        self._invert = bool(m.ha.get("invert"))

    @property
    def available(self) -> bool:
        if not super().available or (v := self.device.value(self.m.name)) is None:
            return False
        stale = self.m.stale_after_ms
        return stale is None or v.age_s() * 1000 <= stale

    @property
    def is_on(self) -> bool | None:
        v = self.device.value(self.m.name)
        return None if v is None else bool(v.raw) != self._invert

