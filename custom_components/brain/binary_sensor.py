"""Binary sensors: boolean catalog measurements and the applied relay state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BrainConfigEntry
from .catalog import Measurement
from .device import BrainDevice
from .entity import BrainEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: BrainConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    data = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        MeasurementBinarySensor(data.device, data.product.model, m)
        for m in data.product.measurements.values()
        if m.platform == "binary_sensor"
    ]
    if "relay" in data.device.sections:
        entities.append(RelayStateBinarySensor(data.device, data.product.model))
    async_add_entities(entities)


class MeasurementBinarySensor(BrainEntity, BinarySensorEntity):
    def __init__(self, device: BrainDevice, model: str, m: Measurement) -> None:
        super().__init__(device, model, m.name)
        self.m = m
        self._attr_name = m.label
        self._attr_entity_registry_enabled_default = m.ha.get("enabled", True)
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


class RelayStateBinarySensor(BrainEntity, BinarySensorEntity):
    """The relay as the expander last applied it (read-only)."""

    _attr_name = "Pump relay"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, device: BrainDevice, model: str) -> None:
        super().__init__(device, model, "relay_state")

    @property
    def is_on(self) -> bool | None:
        relay = self.device.sections.get("relay") or {}
        return relay.get("on")
