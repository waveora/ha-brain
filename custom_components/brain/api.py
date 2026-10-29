"""HTTP client for a device's local API (`fw-status-api`, `fw-local-control-auth`)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT, STREAM_IDLE_TIMEOUT, VERIFY_ACTION


class BrainError(Exception):
    """The device answered with an error."""


class CannotConnect(BrainError):
    """The device did not answer."""


class InvalidAuth(BrainError):
    """The device rejected the control token."""


class StreamRefused(BrainError):
    """All of the device's event-stream slots are taken (HTTP 503)."""


class BrainApi:
    """One device at `host` (address or `name.local`, optional `:port`)."""

    def __init__(self, session: aiohttp.ClientSession, host: str, token: str | None = None) -> None:
        self._session = session
        self.host = host
        self.token = token

    @property
    def base(self) -> str:
        return f"http://{self.host}"

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def status(self) -> dict[str, Any]:
        """`GET /api/status`."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(f"{self.base}/api/status")
                async with resp:
                    if resp.status != 200:
                        raise BrainError(f"status: HTTP {resp.status}")
                    return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(str(err)) from err

    async def action(self, name: str) -> None:
        """`POST /api/action/<name>` with the token when there is one."""
        status, body = await self._post(f"/api/action/{name}")
        if status == 401:
            raise InvalidAuth(body.get("error", "unauthorized"))
        if status != 200 or body.get("ok") is False:
            raise BrainError(body.get("error") or f"HTTP {status}")

    async def verify_token(self) -> bool:
        """Whether the device accepts the token (an unknown action: 404 if authorised)."""
        status, _ = await self._post(f"/api/action/{VERIFY_ACTION}")
        if status == 401:
            return False
        if status in (200, 404):
            return True
        raise BrainError(f"verify: HTTP {status}")

    async def _post(self, path: str) -> tuple[int, dict[str, Any]]:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.post(f"{self.base}{path}", headers=self._auth(), data=b"")
                async with resp:
                    try:
                        body = await resp.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError):
                        body = {}
                    return resp.status, body if isinstance(body, dict) else {}
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(str(err)) from err

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """`GET /api/events`: yields each event until the stream ends or goes quiet.

        Raises `StreamRefused` on 503 and `CannotConnect` when the device does
        not answer or the stream is idle past `STREAM_IDLE_TIMEOUT`.
        """
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(
                    f"{self.base}/api/events",
                    timeout=aiohttp.ClientTimeout(total=None, sock_read=None),
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(str(err)) from err
        async with resp:
            if resp.status == 503:
                raise StreamRefused
            if resp.status != 200:
                raise BrainError(f"events: HTTP {resp.status}")
            data: list[str] = []
            while True:
                try:
                    async with asyncio.timeout(STREAM_IDLE_TIMEOUT):
                        raw = await resp.content.readline()
                except (aiohttp.ClientError, TimeoutError) as err:
                    raise CannotConnect(str(err)) from err
                if not raw:
                    return
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line == "":
                    if data:
                        try:
                            event = json.loads("\n".join(data))
                        except ValueError:
                            event = None
                        data = []
                        if isinstance(event, dict):
                            yield event
                elif line.startswith("data:"):
                    data.append(line[5:].lstrip(" "))
                # `: ping` comments and `retry:` need nothing.
