# Intelbras AMT-8000 — Home Assistant Integration

<img src="https://raw.githubusercontent.com/schmidt-gabriel/amt8000-hass-integration/main/custom_components/amt8000/brand/logo.png" alt="Intelbras" width="240">

[![Validate](https://github.com/schmidt-gabriel/amt8000-hass-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/schmidt-gabriel/amt8000-hass-integration/actions/workflows/validate.yml)
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=schmidt-gabriel&repository=amt8000-hass-integration&category=integration)

Monitor and control an **Intelbras AMT-8000 / AMT-8000 PRO** alarm panel from Home Assistant, over the local network (ISECNet2, port 9009). No cloud and no Intelbras account required.

## Features

- **Alarm panel** — arm (away), disarm, and read the current state (disarmed / armed / triggered).
- **Panic button** — triggers the panel's audible panic.
- **Auto-detected zones** — the integration discovers which zones are actually configured on your panel and creates one entity per zone, **named with the panel's own zone names** (e.g. `Hall`, `Sala`, `Garagem`). No manual zone count to maintain.
- **Per-zone signal** — a signal-level sensor for each zone (useful for wireless sensors).
- **Diagnostics** — firmware version, model, and battery status sensors, plus tamper, siren, and low-battery binary sensors.
- **Single device** — everything is grouped under one `AMT-8000` device, with the Intelbras brand icon (Home Assistant 2026.3+).

## How it works

The panel speaks the unencrypted **ISECNet2** protocol on TCP port 9009. This integration:

- reads frames by their declared length, drains stale data on connect, and closes each session with the proper `bye` command, so it stays in sync with the panel;
- runs all panel I/O off the Home Assistant event loop, serialized by a lock (**the AMT-8000 accepts only one session at a time**);
- polls status every 10 seconds and auto-detects the configured zones and their names from the panel.

Because the panel is single-session, keep the **AMT Remoto Mobile / Guardian app closed** while Home Assistant is polling, otherwise you may see occasional "busy" errors.

## Requirements

- An Intelbras AMT-8000 (or AMT-8000 PRO) reachable on your network, with remote access on port 9009 enabled.
- A **6-digit** panel access password (4-digit-only passwords are not accepted by the protocol).
- Home Assistant. The bundled brand icon requires **HA 2026.3+**; on older versions the integration still works, just without the local logo.
- HACS (optional, for easy install and updates).

## Installation

### HACS (custom repository)

Click the **Open in HACS** badge above, or add it by hand:

1. HACS → Integrations → ⋮ menu → **Custom repositories**.
2. Add `https://github.com/schmidt-gabriel/amt8000-hass-integration` with category **Integration**.
3. Install **AMT-8000**, then restart Home Assistant.

### Manual

Copy `custom_components/amt8000/` into your Home Assistant `config/custom_components/` folder and restart.

## Configuration

Settings → Devices & Services → **Add Integration** → **AMT-8000**, then enter:

| Field | Value |
| --- | --- |
| Host | the panel IP (e.g. `192.168.1.10`) |
| Port | `9009` |
| Password | your 6-digit panel password |

Entities appear automatically under the new **AMT-8000** device.

## Provided entities

| Platform | Entities |
| --- | --- |
| `alarm_control_panel` | the alarm panel (arm away / disarm / triggered state) |
| `button` | Panic |
| `binary_sensor` | one per configured zone (open/closed, with `signal` / `firing` / `bypassed` attributes), plus Tamper, Siren, Low battery |
| `sensor` | Firmware, Model, Battery, and one Signal sensor per zone |

## Notes and limitations

- **Panic sounds the siren.** The panic button (and `alarm_trigger`) fire the real siren — test with care.
- Zones follow the panel's configuration. After adding or removing zones on the panel, reload the integration (or restart Home Assistant) to pick up the change.
- Per-zone **battery/tamper** flags are not decoded yet; global battery and tamper are exposed. Per zone you get open/closed, bypass, and signal.

## Acknowledgments

- https://github.com/merencia/amt8000-hass-integration — the original integration this builds on
- https://github.com/elvis-epx/alarme-intelbras — ISECNet2 protocol reference
- https://github.com/caarlos0/homekit-amt8000
- https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_1/

## Contributions

Contributions are welcome. Open an issue or a pull request.

## License

MIT (see [LICENSE](LICENSE.md)).

This project started under a custom **Intelbras Usage Restriction License**, written as a protest against the lack of public API documentation for the AMT-8000: it forbade use by anyone with a professional relationship with Intelbras. That license had no recognized SPDX identifier, which kept the project out of the HACS default store, so it was relicensed under MIT.

The protest stands, now as a request rather than a restriction. Everything this integration does was reverse engineered from an undocumented protocol. If you work for or with Intelbras, please publish proper API documentation.
