# Architecture

A map of what lives where and how a telegram flows through the system. For the why behind specific choices, see `adr/`.

## Components

- `main.py` wires everything: FastAPI app, lifespan startup/shutdown, and the outbound command router `_handle_device_command`. It also publishes HA discovery for all devices on startup, on the HA birth message, and on MQTT reconnect.
- `core/serial_handler.py` owns the transport. It connects over serial or TCP, parses ESP3 packets into `RadioTelegram`, runs the receive loop with reconnect/backoff, detects teach-in, and builds/sends outbound telegrams (`send_telegram`, `send_a5_dimmer_command`, `send_d2_01_command`, `send_d2_05_command`, F6 rocker sequences, UTE response).
- `core/eep_manager.py` loads the bundled `data/EEP.xml` plus user overrides and custom profiles from `/data/custom_eep`, and exposes profiles for decoding.
- `core/mapping_manager.py` turns an EEP into HA discovery configs (`get_ha_discovery_configs`) and holds `DEFAULT_MAPPINGS` (71 profiles). It builds ChristopheHD-compatible unique IDs.
- `core/mqtt_handler.py` connects to MQTT, publishes state and discovery, persists last states, handles the HA birth message, and merges multi-channel state.
- `core/device_manager.py` stores devices (YAML in `/data`), with an address to device-name(s) map. One address can map to several devices (multi-channel).
- `core/telegram_buffer.py` a ring buffer of recent telegrams for the dashboard and unknown-device detection.
- `api/` FastAPI routers for devices, EEP profiles, mappings, system (status, config, MQTT config, EEP.xml up/download, backups, restart), and gateway (teach-in websocket, base id, actuator test, recent telegrams).
- `templates/index.html` the whole web UI (see `FRONTEND_REFACTOR_PLAN.md`).

## Persistence

`/data` is the add-on's persistent volume (survives updates). Devices, mappings, overrides, last states, custom EEP profiles, and an optional user `EEP.xml` live there. `run.sh` also migrates the old `/config/enocean` path once.

## Telegram lifecycle

Inbound: transport bytes to ESP3 packet to `RadioTelegram` to EEP decode to MQTT state, published to every device on the sender address. Teach-in telegrams are answered or surfaced to the teach-in websocket instead of decoded as data.

Outbound: HA writes an MQTT command to `enoceanmqtt/<device>/set`. `_handle_device_command` resolves the device, then routes EEP-first: `D2-01-xx` and `D2-05-xx` get addressed VLD telegrams; everything else falls back to the role-based path (A5-38-08 for light, F6 rocker simulation for switch/cover). See ADR-0003.

## Home Assistant integration

- Ingress: the UI runs behind HA's Ingress proxy under a dynamic base path. All API and static URLs are built Ingress-aware at runtime (`getApiUrl`, `getWsUrl`, and the js-yaml/i18n loaders). Any new static asset must be loaded the same way.
- MQTT discovery: entities are created via retained discovery configs. Per-device availability uses `enoceanmqtt/<device>/availability`; the gateway LWT uses `enoceanmqtt/__system/status`.
- Theme: the UI mirrors HA's light/dark theme by reading HA's CSS variables from the Ingress parent. See ADR-0002.

## MQTT topics

- State: `enoceanmqtt/<device>/state` (retained JSON).
- Command: `enoceanmqtt/<device>/set` and `enoceanmqtt/<device>/set/<entity>`.
- Availability: `enoceanmqtt/<device>/availability`.
- Gateway status (LWT): `enoceanmqtt/__system/status`.
- Discovery: `homeassistant/<component>/enocean/<unique_id>/config`.
