"""Sensors: catalog measurements, energy from real power, relay `last_off`."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BrainConfigEntry
from .catalog import Measurement
from .const import (
    DEFAULT_WATER_MULTIPLIER,
    DEFAULT_WATER_UNIT,
    ENERGY_MAX_GAP_S,
    OPT_WATER_MULTIPLIER,
    OPT_WATER_UNIT,
    SAME_REPORT_S,
)
from .device import BrainDevice
from .entity import BrainEntity

WATER_METER = "consumption"


async def async_setup_entry(
    hass: HomeAssistant, entry: BrainConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    data = entry.runtime_data
    entities: list[SensorEntity] = []
    for m in data.product.measurements.values():
        if m.platform != "sensor":
            continue
        if m.name == WATER_METER:
            entities.append(
                WaterMeterSensor(
                    data.device,
                    data.product.model,
                    m,
                    entry.options.get(OPT_WATER_UNIT, DEFAULT_WATER_UNIT),
                    entry.options.get(OPT_WATER_MULTIPLIER, DEFAULT_WATER_MULTIPLIER),
                )
            )
        else:
            entities.append(MeasurementSensor(data.device, data.product.model, m))
        if m.ha.get("energy"):
            entities.append(EnergySensor(data.device, data.product.model, m, data.product.measurements))
    if "relay" in data.device.sections and "last_off" in (data.device.sections["relay"] or {}):
        entities.append(RelayLastOffSensor(data.device, data.product.model))
    async_add_entities(entities)


def is_current(device: BrainDevice, m: Measurement) -> bool:
    """Whether `m`'s value belongs to the latest report (see `currentWith` in the catalog)."""
    if m.current_with is None:
        return True
    own, partner = device.value(m.name), device.value(m.current_with)
    if own is None or partner is None:
        return own is not None
    return own.produced >= partner.produced - SAME_REPORT_S


class MeasurementSensor(BrainEntity, SensorEntity):
    """One catalog measurement."""

    def __init__(self, device: BrainDevice, model: str, m: Measurement) -> None:
        super().__init__(device, model, m.name)
        self.m = m
        ha = m.ha
        self._attr_name = m.label
        self._attr_entity_registry_enabled_default = ha.get("enabled", True)
        if ha.get("entity_category") == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._dc = SensorDeviceClass(ha["device_class"]) if "device_class" in ha else None
        self._attr_device_class = self._dc
        if (state_class := ha.get("state_class")) and self._dc is not SensorDeviceClass.ENUM:
            self._attr_state_class = SensorStateClass(state_class)
        if self._dc is SensorDeviceClass.ENUM:
            self._attr_options = sorted(set(m.codes.values()))
        else:
            self._attr_native_unit_of_measurement = ha.get("unit") or m.unit or None
            self._attr_suggested_display_precision = m.decimals

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        v = self.device.value(self.m.name)
        if v is None:
            return False
        stale = self.m.stale_after_ms
        if stale is not None and v.age_s() * 1000 > stale:
            return False
        # A leftover from an earlier report: power reads 0 (the load is off),
        # anything else has no current value.
        return is_current(self.device, self.m) or self._dc is SensorDeviceClass.POWER

    @property
    def native_value(self) -> Any:
        v = self.device.value(self.m.name)
        if v is None:
            return None
        if self._dc is SensorDeviceClass.ENUM:
            return self.m.codes.get(int(v.raw))
        if not is_current(self.device, self.m):
            return 0
        return self.m.display(v.raw)


class WaterMeterSensor(MeasurementSensor):
    """The meter register, in the unit and multiplier the user chose."""

    def __init__(self, device: BrainDevice, model: str, m: Measurement, unit: str, multiplier: float) -> None:
        super().__init__(device, model, m)
        self._attr_native_unit_of_measurement = unit
        self._multiplier = multiplier
        self._attr_suggested_display_precision = max(0, len(f"{multiplier:g}".partition(".")[2]))

    @property
    def native_value(self) -> Any:
        v = self.device.value(self.m.name)
        return None if v is None else round(float(v.raw) * self._multiplier, 6)


class EnergySensor(BrainEntity, RestoreSensor):
    """kWh from a real-power series, each value held until the next report.

    A power value counts only while it belongs to the latest report of its
    load (`current_with`); otherwise the load is off and adds nothing. Gaps
    longer than `ENERGY_MAX_GAP_S` (device unreachable, reports lost) add
    nothing either.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3

    def __init__(self, device: BrainDevice, model: str, power: Measurement, catalog: dict[str, Measurement]) -> None:
        super().__init__(device, model, f"{power.name}_energy")
        self.power = power
        self._attr_name = power.label.replace("real power", "energy")
        self._attr_entity_registry_enabled_default = power.ha.get("enabled", True)
        self._watch = {power.name} | ({power.current_with} if power.current_with else set())
        self._kwh = 0.0
        self._last: tuple[float, float] | None = None  # (monotonic s, W)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None and last.native_value is not None:
            self._kwh = float(last.native_value)
        self.async_on_remove(self.device.add_value_listener(self._on_value))

    def _watts(self) -> float:
        v = self.device.value(self.power.name)
        if v is None or not is_current(self.device, self.power):
            return 0.0
        return max(0.0, float(self.power.display(v.raw)))

    @callback
    def _on_value(self, name: str) -> None:
        if name not in self._watch:
            return
        now = time.monotonic()
        if self._last is not None:
            t0, w0 = self._last
            dt = now - t0
            if 0 < dt <= ENERGY_MAX_GAP_S:
                self._kwh += w0 * dt / 3_600_000
        self._last = (now, self._watts())

    @property
    def native_value(self) -> float:
        return round(self._kwh, 6)


class RelayLastOffSensor(BrainEntity, SensorEntity):
    """Why the pump relay last went off (`request`, `interlock`, `boot`)."""

    _attr_name = "Relay last off"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["boot", "request", "interlock"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: BrainDevice, model: str) -> None:
        super().__init__(device, model, "relay_last_off")

    @property
    def native_value(self) -> str | None:
        return (self.device.sections.get("relay") or {}).get("last_off")
