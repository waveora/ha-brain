# Brain — Septic Brain for Home Assistant

A Home Assistant integration for Septic Brain monitors. It talks only to the
monitor on your network (local push over its event stream); no cloud account is involved.

## Install

1. In HACS, add this repository as a custom repository (category: Integration) and install **Brain**.
2. Restart Home Assistant.
3. Monitors on your network are discovered automatically (Settings → Devices & services). Or add
   **Brain** and enter the monitor's address, e.g. `septic-7be0.local`.

## Entities

Each monitor reports which measurements its setup produces (current sensors fitted and their
roles, voltage-input roles, pressure, aerator, level-loop supply). Entities for the others are
added disabled, and follow when the setup changes on the monitor; an entity you disable stays
disabled. Monitors on older firmware get every entity their setup does not rule out.

## Read-only

The integration only reads the monitor: it has no pairing step and no controls (no pump relay
switch, no settings). Change the monitor's setup on its own page.

## Issues

Report problems at https://github.com/waveora/ha-brain/issues, with the monitor's firmware
version (shown on its page) and Home Assistant's log lines for `custom_components.brain`.

This repository is published from the Septic Brain source tree; the entity catalog
(`custom_components/brain/catalog.json`) is generated there from the monitor's measurement list.
