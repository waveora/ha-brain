"""Config flow: zeroconf discovery or a host."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import async_catalog
from .api import BrainApi, BrainError, CannotConnect
from .const import DOMAIN, STATUS_FORMAT_VERSION


class BrainConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._title: str | None = None

    def _api(self, host: str) -> BrainApi:
        return BrainApi(async_get_clientsession(self.hass), host)

    async def _identify(self, host: str) -> tuple[dict[str, Any] | None, str | None]:
        """The device's status, or an abort reason / form error."""
        try:
            snap = await self._api(host).status()
        except CannotConnect:
            return None, "cannot_connect"
        except BrainError:
            return None, "cannot_connect"
        if snap.get("v") != STATUS_FORMAT_VERSION:
            return None, "unsupported_firmware"
        product = (snap.get("device") or {}).get("product", "")
        catalog = await async_catalog(self.hass)
        if product not in catalog:
            return None, "unsupported_product"
        self._title = f"{catalog[product].model} {snap['device']['id'][-4:]}"
        return snap, None

    async def _after_identify(self, snap: dict[str, Any]) -> ConfigFlowResult:
        await self.async_set_unique_id(snap["device"]["id"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        return self.async_create_entry(title=self._title or self._host, data={CONF_HOST: self._host})

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            snap, problem = await self._identify(self._host)
            if snap is not None:
                return await self._after_identify(snap)
            errors["base"] = problem or "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST): str}), errors=errors
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        props = discovery_info.properties
        device_id = props.get("id")
        if not device_id:
            return self.async_abort(reason="not_brain_device")
        self._host = discovery_info.host
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        if props.get("api") != str(STATUS_FORMAT_VERSION):
            return self.async_abort(reason="unsupported_firmware")
        catalog = await async_catalog(self.hass)
        product = catalog.get(props.get("product", ""))
        if product is None:
            return self.async_abort(reason="unsupported_product")
        self._title = f"{product.model} {device_id[-4:]}"
        self.context["title_placeholders"] = {"name": self._title}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="zeroconf_confirm", description_placeholders={"name": self._title or ""})
        assert self._host is not None
        snap, problem = await self._identify(self._host)
        if snap is None:
            return self.async_abort(reason=problem or "cannot_connect")
        return await self._after_identify(snap)
