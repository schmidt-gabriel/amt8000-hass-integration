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
- **Problems** — a panel-level `Problema` sensor that lights up for the faults the Intelbras app shows (zone, siren, repeater and keypad supervision / tamper / low battery, panel tamper and battery), per-device-type `Sirenes` / `Repetidores` / `Teclados` fault sensors, and per-zone battery (`Bateria <zona>`) and supervision (`Supervisão <zona>`) sensors.
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
| `binary_sensor` | one per configured zone (open/closed, with `signal` / `firing` / `bypassed` / `tamper` / `low_battery` / `comm_failure` attributes); per zone also `Tamper <zona>`, `Bateria <zona>` (low battery) and `Supervisão <zona>` (communication failure); plus Tamper, Siren, Low battery and `Problema`; and `Sirenes`, `Repetidores`, `Teclados` (diagnostic fault sensors, one per device type, created when the panel's status payload carries those bits) |
| `sensor` | Firmware, Model, Battery, and one Signal sensor per zone |

## Notes and limitations

- **Panic sounds the siren.** The panic button (and `alarm_trigger`) fire the real siren — test with care.
- Zones follow the panel's configuration. After adding or removing zones on the panel, reload the integration (or restart Home Assistant) to pick up the change.
- Per-zone tamper is decoded from the extended status (0x0B7A, bytes 89–96) and verified on real hardware.

### Problem detection

The `Problema` binary sensor (diagnostic) turns on when any of these is active:

- zone tamper (0x0B7A) or panel tamper;
- panel battery low/dead;
- zone supervision / communication failure (configured zones only);
- any siren, repeater or keypad supervision failure, tamper or low battery;
- the panel's general problem flag (0x0B4A byte 20 bit 0).

Its `active_problems` attribute lists what is going on in Portuguese, e.g. `Falha de supervisão: Sirene 1`, `Violação (tamper): Repetidor 2`, `Bateria fraca: Teclado 1`, `Violação (tamper): Hall`, `Falha de supervisão: Garagem`, `Violação (tamper) da central`, `Bateria da central fraca`. Per-zone low battery (`Bateria fraca: Sala`) is still unverified, so it is listed but never turns the sensor on by itself. If only the general flag is set and nothing decodes, it shows `Problema não identificado`. The sensor also carries the raw device lists as attributes (`comm_failure_sirens`, `tamper_repeaters`, `low_battery_keypads`, …).

**Byte 20 bit 0 is not reliable.** On firmware 3.2.72 the Intelbras app showed "Sirene 1 — Supervisão: Falha" while that bit was 0, so the app derives its problem list from the fault blocks below. The flag is kept (and visible in diagnostics as `problem`) but no longer the main driver.

The `Sirenes`, `Repetidores` and `Teclados` sensors (diagnostic, enabled by default) turn on when any device of that type reports a supervision failure, tamper or low battery; their `faults` attribute lists them. They are only created when the status payload is long enough to carry those bits.

`Supervisão <zona>` sensors are **enabled by default** (their block is the one where the siren supervision failure was confirmed live). `Bateria <zona>` sensors stay **disabled by default** until verified; enable them from the entity settings if you want to try them. Both report *unknown* if your firmware's payload is too short to contain the bitmap.

#### Fault block layout (0x0B4A payload)

Each fault block is 16 bytes: an 8-byte zone bitmap, then 2 bytes each for keypads, sirens and repeaters, then 2 unknown bytes. Bit *n* of a group is device *n*+1 (zone 1 = first byte bit 0; siren 1 = first siren byte bit 0).

| Block | Zones | Keypads | Sirens | Repeaters | Unknown |
| --- | --- | --- | --- | --- | --- |
| Supervision / comm failure | 73–80 | 81–82 | 83–84 | 85–86 | 87–88 |
| Tamper | 89–96 | 97–98 | 99–100 | 101–102 | 103–104 |
| Low battery | 105–112 | 113–114 | 115–116 | 117–118 | 119–120 |

Verification status:

- **Confirmed live:** siren supervision failure — byte 83 bit 0 = siren 1 (firmware 3.2.72). Zone tamper, bytes 89–96, confirmed on the extended status (0x0B7A), which is where per-zone tamper is read from.
- **Inferred** from the block layout (and, for siren/repeater tamper and battery, matching the caarlos0/homekit-amt8000 offsets): all other keypad, siren and repeater bits, and zone supervision.
- **Unverified:** zone low battery (105–112).

Other fields:

| Field | Source (0-based offsets in the 0x0B4A payload) | Status |
| --- | --- | --- |
| General problem flag | byte 20, bit 0 | did not reflect the app's problem on 3.2.72 |
| Panel clock (`panelTime` in diagnostics) | bytes 64–69, BCD `dd mm yy hh mm ss` | unverified |

AC failure and missing battery are intentionally **not** exposed: their offsets are disputed and need live verification.

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
