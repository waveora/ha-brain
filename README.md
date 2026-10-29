# Brain — Septic Brain and Water Aware for Home Assistant

A Home Assistant integration for Septic Brain and Water Aware monitors. It talks only to the
monitor on your network (local push over its event stream); no cloud account is involved.

## Install

1. In HACS, add this repository as a custom repository (category: Integration) and install **Brain**.
2. Restart Home Assistant.
3. Monitors on your network are discovered automatically (Settings → Devices & services). Or add
   **Brain** and enter the monitor's address, e.g. `septic-7be0.local`.

## Pairing (controls)

Readings work without pairing. To let Home Assistant use the monitor's controls (current sensors
fitted, relay time limit, and — if you opt in — the pump relay), pair the monitor:

1. Open the monitor's page in a browser (its address, or its setup network `SepticBrain`).
2. Power-cycle the monitor, then within 10 minutes choose **Pair with Home Assistant** on its page.
   (On its setup network you can pair at any time.)
3. Copy the control token shown — it is shown once — and enter it when Home Assistant asks.

Once paired, controls from your network need the token, whoever sends them.

## Pump relay

The relay switch is off unless you enable **Allow pump relay control** in the integration's options.
Whatever turns the relay on, the monitor turns it off by itself after its maximum on-time (30 minutes
by default, adjustable as the *Relay maximum on-time* entity), and reports *Relay last off:
interlock*.

## Water meter

Choose the register's unit and multiplier in the integration's options (default gallons × 1) so the
reading can be added to Home Assistant's water consumption.

## Issues

Report problems at https://github.com/septicbrain/ha-brain/issues, with the monitor's firmware
version (shown on its page) and Home Assistant's log lines for `custom_components.brain`.

This repository is published from the Septic Brain source tree; the entity catalog
(`custom_components/brain/catalog.json`) is generated there from the monitor's measurement list.
