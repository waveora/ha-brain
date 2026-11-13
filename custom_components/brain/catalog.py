"""The measurement catalog exported from `@brain/status-model` (`catalog.json`).

Generated: edit the TypeScript catalog and run
`npm run export:ha-catalog -w @brain/status-model`, never this file's data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).parent / "catalog.json"


@dataclass(frozen=True)
class Measurement:
    """One measurement's meaning and its Home Assistant mapping."""

    name: str
    label: str
    unit: str
    scale: float
    offset: float
    decimals: int
    ha: dict[str, Any]
    codes: dict[int, str] = field(default_factory=dict)
    onoff: tuple[str, str] | None = None
    stale_after_ms: int | None = None
    current_with: str | None = None

    @property
    def platform(self) -> str:
        return self.ha["platform"]

    def display(self, raw: float | bool) -> float | int:
        """Raw wire value → display value (catalog scale, offset, decimals)."""
        value = float(raw) * self.scale + self.offset
        return round(value) if self.decimals == 0 else round(value, self.decimals)


AERATOR_SERIES = frozenset({"aer_on", "aer_unusual", "aer_dev", "irms_aer", "power_aer", "reactive_aer", "pf_aer"})


def published(sections: dict[str, Any]) -> frozenset[str] | None:
    """`setup.publishes`: the names the board sends under its setup, or `None` when it does
    not say (older firmware)."""
    names = (sections.get("setup") or {}).get("publishes")
    if not isinstance(names, list):
        return None
    return frozenset(n for n in names if isinstance(n, str))


def creates(name: str, sections: dict[str, Any]) -> bool:
    """Whether a measurement gets an entity. With `setup.publishes` every catalog entry does
    (one the board does not publish is registered disabled, see `enabled_default`);
    without it, what `hidden_by_setup` rules out gets none."""
    return published(sections) is not None or not hidden_by_setup(name, sections)


def enabled_default(m: Measurement, sections: dict[str, Any]) -> bool:
    """Registered enabled: the catalog's default, and published when the board says."""
    names = published(sections)
    return m.ha.get("enabled", True) and (names is None or m.name in names)


def hidden_by_setup(name: str, sections: dict[str, Any]) -> bool:
    """Whether the board's setup rules a measurement out, for firmware without
    `setup.publishes`: pressure series when pressure is off, the probe temperature when the
    sensor is not read, the aerator's series without an aerator. Unknown setup: nothing."""
    setup = sections.get("setup") or {}
    pressure = setup.get("pressure") or {}
    if name.startswith("press") and pressure.get("active") is False:
        return True
    if name in AERATOR_SERIES and (setup.get("aerator") or {}).get("fitted") is False:
        return True
    return name == "temp" and pressure.get("sensor") is False


@dataclass(frozen=True)
class Product:
    slug: str
    model: str
    measurements: dict[str, Measurement]


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Product]:
    """Read the catalog (blocking: call it in an executor)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    products: dict[str, Product] = {}
    for slug, p in data["products"].items():
        measurements = {
            name: Measurement(
                name=name,
                label=m["label"],
                unit=m["unit"],
                scale=m["scale"],
                offset=m["offset"],
                decimals=m["decimals"],
                ha=m["ha"],
                codes={int(k): v for k, v in m.get("codes", {}).items()},
                onoff=tuple(m["onoff"]) if "onoff" in m else None,
                stale_after_ms=m.get("stale_after_ms"),
                current_with=m.get("current_with"),
            )
            for name, m in p["measurements"].items()
        }
        products[slug] = Product(slug=slug, model=p["model"], measurements=measurements)
    return products
