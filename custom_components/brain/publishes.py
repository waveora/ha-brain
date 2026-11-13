"""Measurement entities follow `setup.publishes`: what the board sends under its setup.

An entity for a name the board does not publish is disabled by the integration; once the
board publishes it again, an entity the integration disabled is enabled (when the catalog
enables it by default). An entity the user disabled is never enabled here. Firmware without
the list: nothing changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .catalog import published

if TYPE_CHECKING:
    from . import BrainConfigEntry


@callback
def async_sync_enabled(hass: HomeAssistant, entry: BrainConfigEntry, names: frozenset[str]) -> None:
    """Enable or disable this entry's measurement entities to match `names`."""
    data = entry.runtime_data
    measurements = data.product.measurements
    prefix = f"{data.device.device_id}_"
    reg = er.async_get(hass)
    for e in er.async_entries_for_config_entry(reg, entry.entry_id):
        key = e.unique_id.removeprefix(prefix)
        # Energy sensors follow their real-power series.
        name = key.removesuffix("_energy")
        m = measurements.get(name)
        if m is None or (key != name and not m.ha.get("energy")):
            continue
        if name not in names:
            if e.disabled_by is None:
                reg.async_update_entity(e.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
        elif e.disabled_by is er.RegistryEntryDisabler.INTEGRATION and m.ha.get("enabled", True):
            # HA reloads the entry shortly after to add the entity.
            reg.async_update_entity(e.entity_id, disabled_by=None)


@callback
def async_track_publishes(hass: HomeAssistant, entry: BrainConfigEntry) -> None:
    """Sync now and whenever the device's list changes (a `setup` section event or snapshot)."""
    device = entry.runtime_data.device
    last: dict[str, Any] = {"setup": object(), "names": None}

    @callback
    def check() -> None:
        setup = device.sections.get("setup")
        if setup is last["setup"]:
            return
        last["setup"] = setup
        names = published(device.sections)
        if names is None or names == last["names"]:
            return
        last["names"] = names
        async_sync_enabled(hass, entry, names)

    check()
    entry.async_on_unload(device.add_listener(check))
