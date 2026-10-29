"""Brain: Septic Brain and Water Aware devices over their local API (local push)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BrainApi, BrainError
from .catalog import Product, load_catalog
from .const import CONF_TOKEN, DOMAIN, STATUS_FORMAT_VERSION
from .device import BrainDevice

PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]


@dataclass
class BrainData:
    device: BrainDevice
    product: Product


type BrainConfigEntry = ConfigEntry[BrainData]


async def async_catalog(hass: HomeAssistant) -> dict[str, Product]:
    """The exported measurement catalog, read once."""
    if (catalog := hass.data.get(DOMAIN)) is None:
        catalog = hass.data[DOMAIN] = await hass.async_add_executor_job(load_catalog)
    return catalog


async def async_setup_entry(hass: HomeAssistant, entry: BrainConfigEntry) -> bool:
    api = BrainApi(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data.get(CONF_TOKEN))
    try:
        snapshot = await api.status()
    except BrainError as err:
        raise ConfigEntryNotReady(f"{entry.data[CONF_HOST]} did not answer: {err}") from err
    if snapshot.get("v", 0) > STATUS_FORMAT_VERSION:
        raise ConfigEntryError(f"status format {snapshot.get('v')} is newer than this integration reads")
    identity = snapshot.get("device") or {}
    if identity.get("id") != entry.unique_id:
        raise ConfigEntryNotReady(f"{entry.data[CONF_HOST]} is now device {identity.get('id')}, not {entry.unique_id}")
    product = (await async_catalog(hass)).get(identity.get("product", ""))
    if product is None:
        raise ConfigEntryError(f"unsupported product {identity.get('product')!r}")

    device = BrainDevice(hass, api, snapshot)
    entry.runtime_data = BrainData(device, product)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(hass, device.run(), f"{DOMAIN} {device.device_id} status")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BrainConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
