# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration (distributed via HACS) that exposes a DeLonghi PAC N81 portable AC as a `climate` entity. The integration has no direct connection to the AC; it only sends IR commands. Control flow is one-way (`iot_class: assumed_state`):

```
HA climate entity → build NEC IR frame → raw µs timings → Tuya base64 code → MQTT publish → Zigbee IR blaster → AC
```

There is no feedback from the device, so all state is **optimistic** — the entity assumes its commands succeed and never reads back the AC's actual state.

## Architecture

Three source files under `custom_components/n81_ac/`. The directory name must equal the `domain` in `manifest.json` (`n81_ac`) — Home Assistant only loads an integration from `custom_components/<domain>/`:

- **`climate.py`** — `N81ACEntity` (subclasses `ClimateEntity`, `RestoreEntity`). Registered as a YAML platform via `async_setup_platform` (the integration is `config_flow: false`, so it is configured in `configuration.yaml`, not the UI). On any HA service call (`async_set_hvac_mode`, `async_set_temperature`, `async_set_fan_mode`), it updates internal `_attr_*` state, writes HA state, then calls `update_control_command()`. `RestoreEntity` restores hvac_mode / temperature / fan_mode across HA restarts. The entity does **not** evaluate templates despite `PLATFORM_SCHEMA` still defining many `*_template` options — those options are accepted for config-compatibility but ignored (`TemplateEntity` was dropped because recent HA versions changed its `__init__` signature and broke setup).

- **`update_control_command()`** is the bridge: it translates HA enums into the AC's wire values and publishes over MQTT. Note the **non-obvious mappings** — fan: high=1, medium=2, low=4; mode: fan_only=1, dry=2, cool=8. The MQTT topic defaults to `zigbee2mqtt/IR Control/set/ir_code_to_send` (`IR Control` is the hardcoded-by-default Zigbee device name; overridable via the `mqtt_topic_name` config option).

- **`ir.py`** — pure, HA-independent IR codec. Three stages, called in order:
  1. `create_message(...)` packs power/temp/mode/fan/timer/unit into a 32-bit NEC payload. Temperatures and timer values are stored **bit-reversed** (`reverse_bits`). Celsius temp is offset by −16 before encoding (valid 16–32 °C → 61–89 °F).
  2. `nec_to_raw()` expands the 32-bit value into a list of raw IR pulse/space durations (µs) using NEC protocol timings (9ms leader, 4.5ms space, 560µs bit pulses).
  3. `encode_ir()` / `decode_ir()` convert raw timings ↔ the base64 "Tuya stream" string the blaster expects, using a custom LZ-style `compress`/`decompress`. This codec is vendored from external gists (credited at the top of the file) — treat it as a black box; the AC-specific logic is `create_message` and `nec_to_raw`.

- **`const.py`** — `DOMAIN = "n81_ac"`, platforms list.

## Development notes

- There is **no build, test, or lint setup** in this repo — it is plain Python loaded directly by Home Assistant. The only dependency is the Home Assistant runtime (declared in `manifest.json`, which also declares the `mqtt` dependency).
- To test the IR codec in isolation, run `ir.py` logic directly (see the commented example block at the bottom of `ir.py`); it imports only stdlib.
- To validate the full integration you need a running Home Assistant instance with the integration in its `config/custom_components/` directory and an MQTT broker + zigbee2mqtt IR blaster.
- When changing AC behavior, the wire-value mappings live in **both** `update_control_command()` (HA enum → int) and `create_message()` (int → bits) — keep them consistent.
