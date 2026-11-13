"""HTTP client for a device's local API (`fw-status-api`): read-only."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT, STREAM_IDLE_TIMEOUT


class BrainError(Exception):
    """The device answered with an error."""


class CannotConnect(BrainError):
    """The device did not answer."""


class StreamRefused(BrainError):
    """All of the device's event-stream slots are taken (HTTP 503)."""


class BrainApi:
    """One device at `host` (address or `name.local`, optional `:port`)."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self.host = host

    @property
    def base(self) -> str:
        return f"http://{self.host}"

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
