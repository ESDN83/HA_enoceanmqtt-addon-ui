# Changelog

## [1.6.1-beta1] - 2026-07-22 (beta channel)

> ⚠️ **Fixes a start failure from the 1.6.0 serial-device selector.** A required `device(subsystem=tty)` selector cannot be saved/started empty, so TCP-only setups (or anyone without a device selected) could fail to start after updating. `serial_port` is a plain optional text field (`str?`) again — empty-safe. No action needed; if still stopped, open Configuration and Save once.

Matches stable release 1.6.1.

## [1.6.0-beta4] - 2026-07-22 (beta channel)

### Removed
- **"Detected Serial / USB Devices" card on the Settings page** (added in beta1) — now redundant. Home Assistant's own required serial-device selector in the Configuration tab already lists the connected devices, and a plugged-in USB gateway shows there with a recognizable name (e.g. "USB 300"), so a separate in-app list added no value. Removed the card, its `/api/system/serial-ports` endpoint, and related strings. (Note: the selector is a radio-button list, not a dropdown — wording corrected in DOCS.)

## [1.6.0-beta3] - 2026-07-22 (beta channel)

### Changed
- **Serial device selector is now required (fixes the save error).** Testing confirmed that even on current Home Assistant (core-2026.7.2) an *optional* `device()` selector cannot be saved empty — HA rejects the empty value with `Device '' does not exist`. So `serial_port` is now a **required** `device(subsystem=tty)` selector: the Configuration tab shows a dropdown of connected serial/USB devices and you must pick one. Since a TCP connection takes priority in the startup logic, TCP-only users simply pick any device and it is ignored.
- **Fixed the misleading "Leave empty when using TCP" text** (config field description, Settings-page hint and DOCS) — that field can no longer be left empty. It now explains that a device must be selected and that TCP takes priority. (en/de updated; other languages fall back to their existing text.)
- The Settings-page "Detected Serial / USB Devices" list is now positioned as a **diagnostic** (check your gateway is seen); the actual selection happens in the Configuration tab.

### Known trade-off
A required serial selector means a machine with **no** serial/tty device at all cannot save the config even for TCP-only use. This is a Home Assistant platform limitation (empty device selectors are invalid); on Home Assistant OS at least the on-board serial ports are always listed.

## [1.6.0-beta2] - 2026-07-22 (beta channel)

### Changed
- **Native serial device dropdown in the Configuration tab** — `serial_port` schema switched back from free text (`str?`) to `device(subsystem=tty)?`, so Home Assistant renders a dropdown of the actually-connected serial/USB devices right where you configure the app — the correct place to pick the gateway (the Settings-page list from beta1 can only *show* devices, not feed the config field). The `?` keeps it optional for TCP-only setups. This selector was removed in stable 1.5.2 because an older HA couldn't save it empty next to a TCP port; **please test on the current HA whether a TCP-only config (serial left empty) still saves correctly** before this goes to stable.

## [1.6.0-beta1] - 2026-07-22 (beta channel)

### New Features
- **Detected Serial / USB Devices list** — New read-only card on the Settings page that lists the serial/USB devices the app can see (device path, description, USB VID:PID), highlights the one that looks like an EnOcean gateway (FTDI `0403:6001` or "EnOcean" in the name) and the one currently in use, and offers a one-click **Copy** for each path. This helps — especially non-technical users — find the right value to paste into the "Serial Port" field of the Configuration tab, without re-introducing the old forced dropdown that always demanded a selection even for TCP setups. Prefers the stable `/dev/serial/by-id/…` path (survives reboots); `udev: true` was enabled so those symlinks are available. (community forum request)

## [1.5.2-beta1] - 2026-07-14 (beta channel)

### Fixed
- **Saving the configuration with a TCP transceiver failed** with "Device '' does not exist" when Serial Port was left empty: the Supervisor validated the empty string against the tty device list. `serial_port` is now a plain optional text field.

### Documentation
- Getting Started corrected: TCP transceivers are configured in the separate **TCP Port** field (`tcp:HOST:PORT`), not in Serial Port; `tcp_port` added to the options table.

## [1.5.1-beta1] - 2026-07-14 (beta channel)

### Changed
- **Terminology: "add-on" is now "app"** across the Web UI (EN/DE), documentation, and repository metadata — following Home Assistant's rename of add-ons to Apps in HA 2026.2. No functional changes.

## [1.5.0-beta4] - 2026-07-10 (beta channel)

### Bug Fixes
- **Broken unit strings in the new EEP profiles** — The 62 profiles ported in beta1 carried a text-encoding artifact: `°C` was stored as `Â°C` and `m³` as `mÂ³`, so HA showed garbled units for all new temperature profiles and the gas meter. All 38 occurrences fixed.

This beta matches stable release 1.5.0.

## [1.5.0-beta3] - 2026-07-10 (beta channel)

### Improvements
- **Recent Telegrams show decoded payload** — Each entry on the dashboard now has a second line with the decoded telegram fields (human-readable enum texts preferred, e.g. `R1: Button BI · EB: pressed`, or `TMP: 21.5`) plus the raw hex data. Previously only device, sender ID, RORG and signal strength were shown, so you couldn't see what a telegram actually meant.

## [1.5.0-beta2] - 2026-07-10 (beta channel)

### New Features
- **MQTT Settings in the Web UI** — New card on the Settings page to view and edit all MQTT options (host, port, username, password, discovery prefix, topic prefix, client ID) with **Save**, **Save & Restart Add-on** (via Supervisor API), and **Reset to Defaults** buttons. Reset restores auto-discovery via Home Assistant's broker — previously there was no way to get the original values back once edited in the add-on Configuration tab. Reads/writes the same `/data/options.json` the Configuration tab uses, so both stay in sync (atomic write with `.bak` backup; password never echoed back). Idea from @arno0392's fork, adapted.
- **Download EEP.xml** — New download button next to the upload on the Settings page. Exports the currently active profile database (user-uploaded or bundled), so you can inspect/edit it before re-uploading.

## [1.5.0-beta1] - 2026-07-10 (beta channel)

### New Features
- **EEP profile library: 9 → 71 profiles** — 62 new default HA mappings, contributed by [@arno0392](https://github.com/arno0392)'s fork (thank you!): full A5-02 temperature family (01–30), A5-04-02/03 temp+humidity, A5-06-01 light, A5-07-02/03 occupancy, A5-08-01/02/03 combo sensors, A5-09-02/04/05 air quality (CO₂/VOC), A5-10-01/06 HVAC panels, A5-12-01/02/03 meters (electricity/gas/water with `state_class: total_increasing`), A5-14-01/05/09/0A vibration/window/illuminance, A5-30-01/02 digital inputs, D2-01 electronic switch family (01–0E, 11 two-channel dimmer, 12 two-channel switch), D2-05-01 blinds, F6-03-01/02 four-rocker switches, F6-10-00 window handle. Existing profiles (incl. the F6-02-01/02 per-button binary sensors) are unchanged.
- **Multi-channel state merge (D2-01-11/12)** — Two-channel devices report only the changed channel per telegram (`IO` field selects the channel). The add-on now caches both channels per device and publishes a merged payload (`OV` = channel 0, `OV_CH1` = channel 1), so one channel update no longer wipes the other in HA. Also from @arno0392's fork; channel-1 payload handling is still being field-confirmed — feedback welcome.

## [1.4.0-beta4] - 2026-07-04 (test branch, unreleased)

### Bug Fixes
- **Teach-in timeout no longer spams an unstoppable popup** — Starting teach-in again (or leaving it running) could orphan the 60 s countdown's `setInterval`: its handle was overwritten and could no longer be cleared, so once the counter went negative it fired the "Teach-in timed out — no device detected" toast every second with no way to stop it. `startTeachIn()` now cancels any prior session first, and the countdown clears its own interval on timeout.
- **Web UI showed a stale version** — the displayed version was hard-coded in `main.py` (and `api/system.py`), so it drifted from `config.yaml` (UI still said `1.4.0-beta1`). The version is now read from `config.yaml` at runtime via `app_version.py` (a single source of truth, copied into the image by the Dockerfile), so the UI/API can no longer disagree with the store version.

## [1.4.0-beta3] - 2026-07-04 (test branch, unreleased)

### Bug Fixes (issue #2 — needs field testing)
- **D2-01 switches (e.g. NodOn relay / boiler contact) now use the correct command** — Switch actuators with EEP `D2-01-xx` were driven with F6 rocker *broadcasts*, which they ignore (they are VLD/RORG D2 devices) — and worse, the broadcast (`Dest=FFFFFFFF`) also moved unrelated D2-05 blinds. They now receive a proper addressed `Actuator Set Output` VLD command (`010064` = ON, `010000` = OFF). Fixes both the boiler not switching and the phantom shutter movement reported in #2. Verified against the EnOcean EEP D2-01 profile (python-enocean).

### New Features (issue #2)
- **Reverse direction (invert) option for covers** — Covers can now be flagged **Invert** in the device form. For reverse-wired/mounted shutters this swaps Open/Close and the position mapping on both the command side (`send_d2_05_command`) and the HA position feedback (MQTT discovery `position_template`), so 100 % = open stays correct without rewiring the motor. Per-device, defaults off; the option appears in the Add/Edit device form when the Cover role is selected.

## [1.4.0-beta2] - 2026-07-03 (test branch, unreleased)

### Bug Fixes (D2-05-00, issue #2 — needs field testing)
- **Stop command now uses the correct telegram length** — Per EEP D2-05-00, the `Stop` command (CMD 2) is a **single data byte** (`CHN|CMD`), not the 4-byte `Go to Position and Angle` layout. The beta1 build sent 4 bytes (`7F7F0002`), which the actuator rejected — so Stop physically did nothing (confirmed in @EricGIRARD35's logs). Now sends the correct 1-byte `02`. Verified against the EnOcean EEP spec and the python-enocean reference profile.

### New Features (D2-05-00, issue #2 — needs field testing)
- **UTE (bidirectional) teach-in for NodOn D2-05-00 covers** — NodOn shutter modules put into bidirectional learn mode emit a UTE teach-in **query** (RORG `0xD4`). The beta1 build ignored these (`RORG mismatch: got 0xD4 … skipping decode`), so pairing never completed and the module stayed unresponsive to commands. The add-on now, while a teach-in session is open, answers a UTE query with a proper UTE teach-in **response** (`DB6=0x91` "accepted", EEP fields echoed) addressed back to the module, binding the gateway Sender ID `base_id + offset`. Telegram bytes verified against the python-enocean `UTETeachInPacket` reference. The teach-in wizard now pre-fills the bound Sender ID and pre-selects the Cover role so the new device is configured with the exact Sender ID the module was told to bind (the mismatch that otherwise breaks control).

### New Features (needs field testing)
- **D2-05-00 Blind Actuators (NodOn/EnOcean VLD)** — Covers configured with EEP `D2-05-xx` now send proper structured VLD (RORG D2) command telegrams instead of simulated F6 rocker presses. This makes **Stop** work and adds a real **Position** slider (0–100 %) in Home Assistant. `Go to Position and Angle` (CMD 1) and `Stop` (CMD 2) are used; HA positions are inverted to the EnOcean convention (0 % = open). Eltako/RPS covers keep the existing F6 rocker-simulation path — the command handler branches on the configured EEP. (#2)

## [1.3.0] - 2026-07-03

### New Features
- **External MQTT Broker Support** — New `mqtt.host`, `mqtt.port`, `mqtt.username`, and `mqtt.password` add-on options. Leave `host` empty to keep the previous behaviour (auto-connect to Home Assistant's Mosquitto broker); set it to connect to a standalone external broker instead (e.g. a Mosquitto container on UNRAID/Synology). The MQTT service dependency was relaxed from `need` to `want` so the add-on also starts on systems with no HA MQTT broker add-on installed. (#3)

### Bug Fixes
- **F6-02-02 / F6-02-01 Button Binary Sensors** — Rocker switches (e.g. Eltako FT55, EEP F6-02-02) now create one momentary `binary_sensor` per button (AI/AO/BI/BO) via MQTT Discovery, ON while the button is held and OFF on release. Previously F6-02-02 had no mapping at all, so only the `RSSI` and `last_seen` diagnostic entities were created. F6-02-01 keeps its existing Rocker A/B text sensors and Energy Bow for backwards compatibility and gains the same four button sensors. (#1)

## [1.2.5] - 2026-04-17

### Improvements
- **Debounced State Persistence** — `last_states.yaml` is no longer written on every single `publish_state()` call. Updates mark the cache dirty and a single background task flushes the full YAML every 10s (and always on shutdown via a cancelled-task fallback). Eliminates SD/flash write amplification for installations with chatty sensors.
- **Startup Hardening** — If the EnOcean gateway is unreachable at addon start, the lifespan no longer crashes the whole app. Instead a background task retries `connect()` with backoff (5s → 60s) until the gateway comes up, so the Web UI stays available for reconfiguration and the supervisor doesn't restart in a loop.
- **Typed Transceiver Errors** — `_send_command()` now raises `NotConnectedError` / `CommandTimeoutError` / `TransportLostError` instead of returning `None` for every failure mode. `read_base_id()` catches each and logs a distinct reason — "Base ID read skipped" vs "timed out" vs "transport lost" — so log output tells you *why*, not just *that* it failed.

### Cleanup
- **Removed Dead `/api/gateway/send` Endpoint** — Had placeholder command bytes that didn't match real EEP encodings and wasn't called from anywhere in the frontend. The working command paths are `/api/gateway/test-actuator` and the MQTT command bridge.

## [1.2.4] - 2026-04-17

### Bug Fixes
- **False-Positive Teach-In for Non-Standard Devices** — A5 teach-in detection checks the LRN bit (bit 3 of data[3]). Some non-standard devices (e.g. Eltako Staufix boiler sensor) send regular data telegrams with LRN=0, which were mis-flagged as teach-ins on every received packet. Now only applies teach-in detection to senders that are NOT already configured — an already-known device cannot logically send a new teach-in.

## [1.2.3] - 2026-04-17

### Bug Fixes
- **Reconnect Base-ID Deadlock** — After a TCP reconnect, the base-ID re-read used to run synchronously inside `_read_loop` via `_wait_and_reconnect`. But `_send_command()` depends on `_read_loop` to deliver the response packet — so awaiting it from inside `_read_loop` deadlocked until the 3s command timeout ("Timeout waiting for response to command 0x08 / Invalid base ID response: None" in the logs). The base-ID refresh now runs as an independent task so the read loop resumes immediately and the response round-trip completes.

## [1.2.2] - 2026-04-17

### Bug Fixes
- **TCP Silent Disconnect Fix** — The read loop no longer silently loops when the TCP peer closes the connection. Previously, when an ESP32 gateway (or any TCP peer) sent a clean FIN, `recv()` returned empty bytes which the code treated as a read timeout — leaving the addon in a zombie state with no log output and no reconnect. `_serial_read()` now raises `ConnectionResetError` in that case so the read loop can trigger a reconnect.
- **TCP Keepalive** — Enabled `SO_KEEPALIVE` on TCP connections with `TCP_KEEPIDLE=30s`, `TCP_KEEPINTVL=10s`, `TCP_KEEPCNT=3`. Half-open connections (ESP32 crash, WiFi drop, router reboot — anything without a clean FIN) are now detected in ~60s instead of the OS default of ~2 hours.
- **Automatic Reconnect** — On transport loss (`ConnectionError`, `SerialException`, `OSError`), the read loop now closes the dead transport and retries the connect with exponential backoff (1s → 2s → … → 30s max). Previously the task died and `/health` kept reporting `enocean_connected: true`.
- **Non-blocking Writes** — `send_telegram()` and `_send_command()` now write via `run_in_executor`. A full send buffer on a half-dead socket no longer freezes the entire FastAPI event loop (UI + MQTT).
- **Command Race Condition** — `_send_command()` is now serialized via an `asyncio.Lock` so concurrent callers cannot clobber each other's `_response_future` slot and mis-route responses.

## [1.2.1] - 2026-03-27

### New Features
- **TCP Port Configuration** — New `tcp_port` config option for connecting to remote EnOcean devices via TCP (e.g., `tcp:192.168.1.118:8638` for SLZB-MR5U USB-Passthrough or similar USB-over-IP devices). TCP takes priority over serial when both are configured.

### Bug Fixes
- **TCP Read Fix** — Fixed TCP socket read in serial handler. The `_serial_read()` method now correctly reads from TCP sockets (previously only serial devices were read, causing TCP connections to receive no data).

## [1.2.0] - 2026-03-10

### New Features
- **Advanced Mapping Fields** — state_class, entity_category, expire_after, force_update, suggested_display_precision, and value_template support in mapping editor
- **Visual & Text Mode Editor** — Toggle between visual form and YAML text editor for mapping overrides (inline and modal)
- **Fork Standard Profiles** — Create custom copies of standard EEP profiles to edit Telegram Fields and HA mappings together
- **YAML-Based Config** — All configuration files migrated from JSON to YAML (devices, mapping overrides) with automatic migration of existing JSON files
- **YAML Export/Import** — Full configuration export/import as YAML files
- **Pass-Through Fields** — Support for pass-through field mappings in the mapping editor

### Improvements
- **Profile Tree Sections** — Dedicated sections for Custom Profiles and Customized Mappings at the top of the EEP tree
- **Orphaned Override Warnings** — Visual warning for mapping overrides that reference non-existent EEP profiles
- **Enhanced Mapping Display** — Profile detail view now shows advanced mapping fields (state_class, expire_after, etc.)
- **Tree Auto-Refresh** — Profile tree refreshes automatically after saving or resetting mapping overrides
- **Text Mode State Reset** — Proper cleanup of text/visual mode state when opening/closing editors

### Bug Fixes
- **HA Ingress Compatibility** — Fixed js-yaml library loading through HA Ingress proxy (dynamic path resolution instead of absolute `/static/` path)
- **Text Mode 400 Error** — Fixed form submission when clicking Text Mode button in Custom Profile modal (missing `type="button"`)
- **Backup Restore** — Custom profiles (custom_eep/) now properly reloaded after restore (EEP manager re-initialization)
- **Version Display** — Fixed version shown in UI sidebar (was stuck at 1.1.0)
- **jsyaml Error Handling** — Added availability checks and try-catch around YAML serialization calls

## [1.1.0] - 2026-03-08

### New Features
- **Multi-Language UI (i18n)** — Auto-detects browser language, supports 11 languages: English, German, Chinese, Hindi, Spanish, French, Arabic, Bengali, Portuguese, Russian, Japanese
- **EEP.xml Upload** — Upload custom EEP.xml via Settings page, with validation, reload, and delete-to-revert
- **EEP.xml in Backups** — Custom EEP.xml is included in export/import ZIP backups
- **HA Entity Mapping Overrides** — Customize HA entity mappings per EEP profile directly from the profile detail view, with inline editor, auto-fill from EEP.xml fields, and save/reset functionality

### Improvements
- **Dark Mode Fixes** — Sidebar uses correct grey (#2b3035) instead of blue, removed `bg-light` from profile cards
- **Consistent dashes** — All feature descriptions use em-dash style

### Bug Fixes
- **Mapping Overrides in Backups** — `mapping_overrides.json` is now included in backup export/import

## [1.0.0] - 2026-03-07

First stable release of **EnOcean MQTT UI** — a complete All-in-One Home Assistant Add-on for EnOcean devices.

### Core Features
- **Modern Web UI** — Bootstrap 5 single-page application with responsive design, sidebar navigation, and mobile hamburger menu
- **Visual Device Wizard** — Add devices via teach-in or manual entry, no YAML editing needed
- **96+ EEP Profiles** — Bundled EEP.xml from [ChristopheHD's enocean library](https://github.com/ChristopheHD/enocean) with F6 (RPS), D5 (1BS), A5 (4BS), D2 (VLD), and D1 (MSC) RORGs
- **Custom EEP Profile Editor** — Create custom profiles with field definitions (enum, value, command types) and built-in HA Entity Mapping builder
- **Home Assistant MQTT Discovery** — Automatic entity creation with per-device availability, LWT, and HA birth message support
- **Live Telegram Monitor** — Real-time ESP3 telegram decoding with signal strength display
- **Unknown Device Detection** — Auto-detect unconfigured EnOcean devices with quick-add buttons

### Actuator Control
- **Eltako dimmer/switch/blind control** — Send F6 rocker telegrams to Eltako FD62NPN, FSR61, FSB61 and similar actuators
- **Actuator teach-in** — Send teach-in telegrams with configurable sender offset (1-127) per device
- **A5-38-08 Central Command Dimming** — Brightness control for Eltako dimmers via HA light entities
- **Test buttons** — ON/OFF/Open/Close/Stop directly from device detail view

### Backup & Settings
- **Local Backup System** — Create, list, download, restore, and delete local backup ZIPs from the Settings page
- **Import/Export** — Download or upload configuration as ZIP files
- **Confirmation popups** — Restore and delete actions require explicit confirmation
- **Device state caching** — Persist sensor states across restarts (essential for infrequent senders like Kessel Staufix)

### UI Polish
- **Dark mode** — Automatically detects HA dark theme (Ingress) or OS `prefers-color-scheme`. All components adapt.
- **Device & profile search** — Filter devices by name/address, search EEP profiles with auto-expanding tree nodes
- **Teach-in countdown timer** — 60-second visual countdown with cancel button
- **Custom Profile highlight** — Yellow button and highlighting for custom profiles

### Architecture
- **ChristopheHD MQTT compatibility** — Uses `enoceanmqtt` prefix, compatible topic patterns and discovery UIDs
- **O(1) device lookup** — Hash map for address-to-device resolution on every telegram
- **Correct value scaling** — XML child element parsing for range/scale values (not attributes)
- **Configurable logging** — Log level properly applied to all loggers including uvicorn
- **Repository metadata** — `repository.json` for "Add to Home Assistant" button

### Credits
- [ChristopheHD](https://github.com/ChristopheHD/enocean) — EEP.xml profile database and MQTT compatibility patterns
- EnOcean Alliance for the EEP specification
- Home Assistant community
