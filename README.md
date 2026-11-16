# Intelbras AMT-8000 — Home Assistant Integration

<img src="https://raw.githubusercontent.com/schmidt-gabriel/amt8000-hass-integration/main/custom_components/amt8000/brand/logo.png" alt="Intelbras" width="240">

[![Validate](https://github.com/schmidt-gabriel/amt8000-hass-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/schmidt-gabriel/amt8000-hass-integration/actions/workflows/validate.yml)
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=schmidt-gabriel&repository=amt8000-hass-integration&category=integration)

Monitor and control an **Intelbras AMT-8000 / AMT-8000 PRO** alarm panel from Home Assistant, over the local network (ISECNet2, port 9009). No cloud and no Intelbras account required.

> **Important Notice:** If you have any affiliation with Intelbras, please read the [LICENSE](LICENSE.md) carefully before proceeding.

## Features

- **Alarm panel** — arm (away), disarm, and read the current state (disarmed / armed / triggered).
- **Panic button** — triggers the panel's audible panic.
- **Auto-detected zones** — the integration discovers which zones are actually configured on your panel and creates one entity per zone, **named with the panel's own zone names** (e.g. `Hall`, `Sala`, `Garagem`). No manual zone count to maintain.
- **Per-zone signal** — a signal-level sensor for each zone (useful for wireless sensors).
- **Diagnostics** — firmware version, model, and battery status sensors, plus tamper, siren, and low-battery binary sensors.
- **Problems** — a panel-level `Problema` sensor mirroring the "problems detected" flag of the Intelbras app, and per-zone battery (`Bateria <zona>`) and supervision (`Supervisão <zona>`) sensors.
- **Download diagnostics** — dumps the latest status with the raw protocol payloads, to help decode new fields.
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
| `binary_sensor` | one per configured zone (open/closed, with `signal` / `firing` / `bypassed` / `tamper` / `low_battery` / `comm_failure` attributes); per zone also `Tamper <zona>`, `Bateria <zona>` (low battery) and `Supervisão <zona>` (communication failure); plus Tamper, Siren, Low battery and `Problema` |
| `sensor` | Firmware, Model, Battery, and one Signal sensor per zone |

## Notes and limitations

- **Panic sounds the siren.** The panic button (and `alarm_trigger`) fire the real siren — test with care.
- Zones follow the panel's configuration. After adding or removing zones on the panel, reload the integration (or restart Home Assistant) to pick up the change.
- Per-zone tamper is decoded from the extended status (0x0B7A, bytes 89–96) and verified on real hardware.

### Problem detection

The `Problema` binary sensor (diagnostic) turns on when the panel's general "problems detected" flag is set (status 0x0B4A, byte 20 bit 0) **or** a verified fault is active (zone tamper, panel tamper, panel battery low/dead). Its `active_problems` attribute lists what is going on, e.g. `Violação (tamper): Hall`, `Violação (tamper) da central`, `Bateria da central fraca`, and — from the unverified bitmaps below, for configured zones only — `Bateria fraca: Sala` or `Falha de supervisão: Garagem`. The unverified bitmaps only label the cause; they never turn the sensor on by themselves. When the flag is on but nothing decodes (for example a wireless siren supervision failure), it shows `Problema não identificado` — so the fault still surfaces in Home Assistant.

The per-zone `Bateria <zona>` and `Supervisão <zona>` sensors are created **disabled by default** until their offsets are verified on real hardware; enable them from the entity settings if you want to try them. They report *unknown* if your firmware's status payload is too short to contain the bitmap.

**Unverified offsets.** These fields come from community protocol notes and have **not** been confirmed on a real panel yet:

| Field | Source (0-based offsets in the 0x0B4A payload) |
| --- | --- |
| General problem flag | byte 20, bit 0 |
| Per-zone low battery (`Bateria <zona>`) | bitmap, bytes 105–112 |
| Per-zone supervision / comm failure (`Supervisão <zona>`) | bitmap, bytes 73–80 |
| Panel clock (`panelTime` in diagnostics) | bytes 64–69, BCD `dd mm yy hh mm ss` |

AC failure, missing battery, siren and repeater faults are intentionally **not** exposed: their offsets are disputed and need live verification.

### Helping decode more faults

Settings → Devices & Services → AMT-8000 → ⋮ → **Download diagnostics** saves a JSON file with the latest status, the raw hex of the 0x0B4A and 0x0B7A payloads, and a full byte-by-byte dump (0-based offsets) of both payloads. Host and password are redacted, but the file still contains your zone names and the raw panel payloads — **review it before posting it publicly**. To map a fault:

1. Download diagnostics with everything normal.
2. Provoke one fault (remove a sensor battery, power off a wireless siren, open a sensor's cover…), wait ~20 s, and download again.
3. Diff the full hex (`status_0b4a` and `ext_status_0b7a`) of the two files — not just the decoded fields — and open an issue with the offsets that changed.

## Acknowledgments

- https://github.com/merencia/amt8000-hass-integration — the original integration this builds on
- https://github.com/elvis-epx/alarme-intelbras — ISECNet2 protocol reference
- https://github.com/caarlos0/homekit-amt8000
- https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_1/

## Contributions

Contributions are welcome. Open an issue or a pull request.

## License

This project uses a custom **Intelbras Usage Restriction License** (see [LICENSE](LICENSE.md)) — a protest against the lack of public API documentation. In short: anyone may use this code **except** individuals or entities with a professional relationship with Intelbras (employees, professional installers of Intelbras systems, or contractors hired by Intelbras). The license is expected to change once Intelbras publishes adequate API documentation.
