"""One device's live status: the stream (or polling) kept applied to a local copy.

Semantics follow `@aware/status-model`'s reducer: a snapshot replaces
everything, events at or below the applied `seq` are dropped, `resync` means
refetch the snapshot. Ages are turned into the monotonic time each value was
produced, so an entity can ask how old a value is at any moment.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant, callback

from .api import BrainApi, BrainError, CannotConnect, StreamRefused
from .const import POLL_INTERVAL, RECONNECT_MAX, RECONNECT_MIN, STREAM_RETRY

_LOGGER = logging.getLogger(__name__)


@dataclass
class Value:
    """A measurement's raw value and when (monotonic s) it was produced."""

    raw: float | bool
    produced: float

    def age_s(self, now: float | None = None) -> float:
        return (time.monotonic() if now is None else now) - self.produced


class BrainDevice:
    """The local copy of one device's status, and the task that keeps it current."""

    def __init__(self, hass: HomeAssistant, api: BrainApi, snapshot: dict[str, Any]) -> None:
        self.hass = hass
        self.api = api
        self.available = True
        self.streaming = False
        self.seq = 0
        self.identity: dict[str, Any] = {}
        self.sections: dict[str, Any] = {}
        self.values: dict[str, Value] = {}
        self._listeners: set[Callable[[], None]] = set()
        self._value_listeners: set[Callable[[str], None]] = set()
        self.apply_snapshot(snapshot)

    # Identity ---------------------------------------------------------------

    @property
    def device_id(self) -> str:
        return self.identity["id"]

    @property
    def product(self) -> str:
        return self.identity["product"]

    @property
    def version(self) -> str | None:
        return self.identity.get("version")

    @property
    def paired(self) -> bool:
        return bool((self.sections.get("network") or {}).get("paired"))

    # Listeners --------------------------------------------------------------

    @callback
    def add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        """Call `update` on any change; returns the remover."""
        self._listeners.add(update)
        return lambda: self._listeners.discard(update)

    @callback
    def add_value_listener(self, update: Callable[[str], None]) -> Callable[[], None]:
        """Call `update(name)` for each measurement event (not snapshots)."""
        self._value_listeners.add(update)
        return lambda: self._value_listeners.discard(update)

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()

    # Reducer ----------------------------------------------------------------

    @callback
    def apply_snapshot(self, snap: dict[str, Any], now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self.identity = dict(snap.get("device") or {})
        self.seq = int(snap.get("seq", 0))
        self.sections = dict(snap.get("sections") or {})
        self.values = {
            m["name"]: Value(m["value"], now - m.get("age_ms", 0) / 1000)
            for m in snap.get("measurements", [])
            if "name" in m and "value" in m
        }

    @callback
    def apply_event(self, event: dict[str, Any], now: float | None = None) -> str:
        """Apply one event: `"applied"`, `"ignored"` or `"resync"`."""
        kind = event.get("type")
        if kind == "resync":
            return "resync"
        seq = event.get("seq")
        if not isinstance(seq, int) or seq <= self.seq:
            return "ignored"
        now = time.monotonic() if now is None else now
        self.seq = seq
        if kind == "measurement" and "name" in event:
            name = event["name"]
            self.values[name] = Value(event["value"], now - event.get("age_ms", 0) / 1000)
            for update in list(self._value_listeners):
                update(name)
        elif kind == "section" and "key" in event:
            self.sections[event["key"]] = event.get("value")
        return "applied"

    # Transport --------------------------------------------------------------

    async def _refresh(self) -> None:
        self.apply_snapshot(await self.api.status())

    @callback
    def _set_available(self, available: bool) -> None:
        if available != self.available:
            _LOGGER.info("%s %s", self.api.host, "reachable" if available else "unreachable")
            self.available = available
        self._notify()

    async def run(self) -> None:
        """Keep the copy current until cancelled: stream, else poll."""
        delay = RECONNECT_MIN
        loop = asyncio.get_running_loop()
        stream_retry_at = 0.0
        while True:
            if loop.time() >= stream_retry_at:
                try:
                    await self._stream()
                    delay = RECONNECT_MIN
                    continue  # the device closed the stream (lifetime cap): reopen
                except StreamRefused:
                    _LOGGER.debug("%s: stream slots taken, polling", self.api.host)
                    stream_retry_at = loop.time() + STREAM_RETRY.total_seconds()
                except BrainError as err:
                    _LOGGER.debug("%s: stream ended: %s", self.api.host, err)
                finally:
                    self.streaming = False
            try:
                await self._refresh()
                self._set_available(True)
                delay = RECONNECT_MIN
                await asyncio.sleep(POLL_INTERVAL.total_seconds())
            except (CannotConnect, BrainError):
                self._set_available(False)
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX)
                stream_retry_at = 0.0

    async def _stream(self) -> None:
        events = self.api.events()
        # Open the stream first, then take the snapshot: the stream starts at
        # "now" and events the snapshot already covers are dropped by seq.
        first = asyncio.ensure_future(anext(events))
        try:
            await asyncio.wait({first}, timeout=0.5)
            await self._refresh()
            self.streaming = True
            self._set_available(True)
            try:
                event = await first
            except StopAsyncIteration:
                return
            while True:
                if self.apply_event(event) == "resync":
                    await self._refresh()
                self._notify()
                try:
                    event = await anext(events)
                except StopAsyncIteration:
                    return
        finally:
            # The generator must not be running when it is closed.
            if not first.done():
                first.cancel()
            await asyncio.gather(first, return_exceptions=True)
            await events.aclose()

    # Derived ----------------------------------------------------------------

    def value(self, name: str) -> Value | None:
        return self.values.get(name)
