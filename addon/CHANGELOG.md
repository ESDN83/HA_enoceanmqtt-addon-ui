# Changelog

## [1.7.3] - 2026-08-01

### Bug Fixes
- **A device whose name contains a slash could still not be opened, renamed or deleted** (#36). 1.7.2 stopped new names from containing `/`, but it did nothing for the devices that already had one, and those stayed completely out of reach: every attempt failed with "Not Found". The name is part of the web address of the request, and a slash inside it splits that address, so the request never arrived at the add-on at all. Those devices can be opened, renamed and deleted again.

  **Please rename them.** The slash also breaks commands: Home Assistant's command topic for such a device does not match what the add-on listens to, so a switch or blind with a slash in its name never receives anything. Renaming it (any separator other than `/`, `+` or `#`) fixes that, and the entities in Home Assistant follow the new name.

## [1.7.2] - 2026-07-30

### Bug Fixes
- **A device could become impossible to edit or delete** (#36). The device name was written straight into the buttons' `onclick` code and into the API address. A name containing an apostrophe ("Volet d'entrée") ended the code string and killed the Edit and Delete buttons outright; a name containing `/` or `#` produced an address that never reached the add-on. Either way the device could no longer be opened, edited or removed from the web UI, and re-teaching the module in did not help because the old entry was still there. Names are now kept out of the markup entirely and properly encoded in every request, so any name works.
- **A failed delete reported success** (#36). The delete button never checked the add-on's answer. When the request failed the UI still showed "Device deleted" and the device stayed in the list, which is what made the problem above look unfixable. Failures are reported with the reason now.
- **Deleted and renamed devices left ghosts behind** (#36). Deleting or renaming a device left its last state cached under the old name, and the add-on republished that cache on every start. The result was a retained state message for a device that no longer exists, and a new device given that same name later inherited the old device's state before its first telegram arrived. Delete and rename now clear the old name completely, a rename carries the last state over to the new name, and any leftovers from earlier versions are cleaned up once at the next start.
- **The state cache could lose a change**. The cache was only ever written after a telegram arrived, so a delete made shortly before stopping the add-on was lost and came back on the next start.

### Changes
- **Device names are checked when saved**. `/`, `+` and `#` are rejected with an explanation, because they are not valid in an MQTT topic and produced an entry that could not be addressed afterwards. Apostrophes, quotes and accented characters are fine.

## [1.7.1] - 2026-07-26

### Bug Fixes
- **Every command was sent to the device twice.** One click in Home Assistant produced two identical radio telegrams. The add-on subscribed to two MQTT topic patterns that both matched the same command topic, and the broker delivers one copy per matching subscription, so every command was handled twice. Most actuators tolerate that, but a dimmer receiving the same command twice in a millisecond can end up at a different brightness than the one you asked for, and repeated switch commands can cancel each other out. Found from a field report on an Eltako FD62NPN and verified on real hardware: the gateway confirmed two separate transmissions per click before the fix, one after.
- **Debug logging drowned in one line per discarded byte.** A gateway that emits stray bytes between packets filled the log faster than it could be read, pushing the actual telegrams out of the buffer — exactly when debug logging was switched on to find something. The bytes are counted now and reported once the packet stream resynchronises, with a short hex sample. That sample immediately identified a TCP gateway that had stopped speaking the protocol at all.
- **"Connected to MQTT broker" was logged twice per start.** Two separate log statements with the same text, which reads like two connections. One of them also printed after a connection *timeout*, claiming a connection that did not exist. Only the broker's own callback reports it now.

## [1.7.0] - 2026-07-26

Two-channel actuator modules (NodOn SIN-2-2-01 and friends) now work end to end, switch actuators report their real state back to Home Assistant, and the dark/light theme finally matches Home Assistant in every panel. Field tested on the beta channel through nine builds. Thanks to **@vincent-lvh** and **@salzrat** for testing every one of them on real hardware.

No action is needed after updating.

### New Features
- **Two-channel D2-01 modules** — A device has a `channel` setting: teach in the module once, then add one device per output with the same address. Commands target the selected output, each channel gets its own Home Assistant entity with its own name, and after saving channel 1 the wizard offers to create channel 2 with everything pre-filled. The two channels appear as one Home Assistant device (labelled by manufacturer and EEP, e.g. "NodOn D2-01-12") with one entity per output.
- **Switch actuators report their state** — Switching an actuator at the module itself, or from another sender, now updates Home Assistant. D2-01 modules are followed per channel via the status telegram's `IO` field, so on a two-channel module each output keeps its own state. Eltako F6 actuators with status reporting (e.g. FSR61) are followed from their confirmation telegrams; a per-device "Invert reported state" option covers actuators taught in the other way round.
- **Devices can be renamed** — The device name (the MQTT topic base) is editable when editing a device, not only at creation. Renaming re-homes the MQTT topics and cleans up the old ones; the Home Assistant entity is preserved. A confirmation dialog warns first.
- **Sender-ID collision warning** — Saving a new Eltako-style actuator whose Sender ID is already taken now asks for confirmation. Broadcast-driven actuators each need their own Sender ID. D2 channel devices are exempt, sharing one Sender ID is correct there.
- **Detected fields are marked** — Values that came from the teach-in telegram are highlighted, so it is obvious what was detected and what was typed by hand.

### Bug Fixes
- **D2-01 actuators did nothing when commanded** (#23) — The command handler branched on the role (light/switch/cover) before looking at the EEP, so a D2-01 module registered as a light was driven with Eltako A5-38-08 dimmer telegrams and never reacted. The EEP is checked first now: every `D2-01-xx` device gets a proper addressed "Actuator Set Output" (VLD) telegram.
- **Only the first device on a module address received state** (#24) — Devices were indexed one per address, so with one device per output the second channel's entity stayed empty.
- **Editing a channel device corrupted naming and left orphans** (#34) — Editing one channel renamed both, and identity edits (address, Sender ID, EEP, channel) left the old Home Assistant entities behind to pile up. The edit path kept dropping the `channel` field, rebuilt discovery without it, and never retracted the entities it replaced. All three are fixed, and deleting one channel keeps the shared diagnostic sensors (RSSI, Last Seen) the remaining channel still needs.
- **Channel naming reverted on every restart** (#34) — The add-on's startup republish carried its own older copy of the naming rule and undid what was configured. Discovery naming now lives in one place that every path calls.
- **A switch showed two buttons instead of a toggle** — Switch entities were published as optimistic, which marks them `assumed_state` in Home Assistant. They are no longer optimistic; the commanded state is echoed to the state topic so the toggle still reacts immediately for actuators that never report back.
- **Eltako status feedback was inverted** — An Eltako actuator confirms with the opposite rocker code to the one used as a command: ON is reported as `0x70` (BO), while the command for ON is `0x50`. The status sync followed the command convention, so an FSR61 reported ON as OFF.
- **A D2-01 module configured as a light was always reported off** — The light path read `SW` and `EDIM`, which only exist in an Eltako A5-38-08 telegram. D2-01 lights now take state and brightness from `OV`.
- **Dark and light theme now match Home Assistant everywhere** (#25) — Three separate causes: read-only and disabled inputs kept Bootstrap's low-contrast colours; the operating system's dark preference could override a light Home Assistant; and theme detection read the `<body>` background, which in Home Assistant is transparent and was parsed as pitch black, so a light Home Assistant rendered dark. Detection now reads Home Assistant's own `--primary-background-color`, and the app's fields are bound to the same variables as the page.
- **Teach-in reused the previous device's role and Sender ID** (#23, #29, #30) — The role dropdown kept the last selection and UTE devices were always pre-set to "cover", so relays were registered as blinds. The sender offset always started at 1 although each actuator needs its own. Canceling an edit also left the previous device's name (locked read-only) in the wizard. The form is fully reset at the start of every entry, the role is derived from the EEP, and the next unused sender offset is suggested.
- **"Invert reported state" was unreachable when editing a switch** — The option only appeared while the role dropdown was being changed, so it could not be reviewed or turned off afterwards.

### Changed
- **No speculative wait during multi-channel teach-in** — A UTE teach-in carries only the number of channels, never a channel index, so a module cannot signal which output a pairing is for. The wizard no longer waits for a telegram that does not exist and says instead that one teach-in covers the whole module.

## [1.6.2] - 2026-07-22

> ⚠️ **Action needed after updating — please read.**
> The **Serial Port** is now picked from a device list instead of a text field. Home Assistant cannot save this kind of field empty, so **after updating you must open the Configuration tab and select a serial device**, otherwise the add-on will not start.
> - **USB:** select your EnOcean stick (it shows with a recognizable name, e.g. "USB 300").
> - **TCP:** a TCP connection takes priority, so just **pick any device** — it is ignored while a TCP port is set.
> Then click **Save** and start the add-on.

### Changed
- **Serial port is picked from a device list** — In response to a community request to choose the EnOcean dongle from a list, `serial_port` is a native `device(subsystem=tty)` selector: the Configuration tab shows the connected serial/USB devices, and a plugged-in gateway appears with a recognizable name. A device must be selected (Home Assistant rejects an empty device value and provides no portable default). TCP takes priority, so TCP-only users pick any device and it is ignored. Enables `udev` so stable `/dev/serial/by-id/...` paths work inside the container.
- Config field description, README and DOCS updated to match.

## [1.5.2] - 2026-07-14

### Fixed
- **Saving the configuration with a TCP transceiver failed** with "Device '' does not exist" when Serial Port was left empty: the Supervisor validated the empty string against the tty device list. `serial_port` is now a plain optional text field.

### Documentation
- Getting Started corrected: TCP transceivers are configured in the separate **TCP Port** field (`tcp:HOST:PORT`), not in Serial Port; `tcp_port` added to the options table.

## [1.5.1] - 2026-07-14

### Changed
- **Terminology: "add-on" is now "app"** across the Web UI (EN/DE), documentation, and repository metadata — following Home Assistant's rename of add-ons to Apps in HA 2026.2. No functional changes.

## [1.5.0] - 2026-07-10

Field-tested in the Beta channel (1.5.0-beta1…beta3) before this stable release.

### New Features
- **EEP profile library: 9 → 71 profiles** — 62 new default HA mappings, contributed by [@arno0392](https://github.com/arno0392)'s fork (thank you!): full A5-02 temperature family, A5-04-02/03 temp+humidity, A5-06-01 light, A5-07-02/03 occupancy, A5-08-01/02/03 combo sensors, A5-09-02/04/05 air quality (CO₂/VOC), A5-10-01/06 HVAC panels, A5-12-01/02/03 meters (electricity/gas/water with `state_class: total_increasing`), A5-14-01/05/09/0A vibration/window/illuminance, A5-30-01/02 digital inputs, D2-01 electronic switch family (01–0E, 11 two-channel dimmer, 12 two-channel switch), D2-05-01 blinds, F6-03-01/02 four-rocker switches, F6-10-00 window handle.
- **Multi-channel state merge (D2-01-11/12)** — Two-channel devices report only the changed channel per telegram (`IO` field selects the channel). The add-on now caches both channels per device and publishes a merged payload (`OV` = channel 0, `OV_CH1` = channel 1), so one channel update no longer wipes the other in HA. Also from @arno0392's fork.
- **MQTT Settings in the Web UI** — New card on the Settings page to view and edit all MQTT options (host, port, username, password, discovery prefix, topic prefix, client ID) with **Save**, **Save & Restart Add-on** (via Supervisor API), and **Reset to Defaults** buttons. Reset restores auto-discovery via Home Assistant's broker — previously there was no way to get the original values back once edited in the add-on Configuration tab. Reads/writes the same `/data/options.json` the Configuration tab uses (atomic write with `.bak` backup; password never echoed back).
- **Download EEP.xml** — New download button next to the upload on the Settings page. Exports the currently active profile database (user-uploaded or bundled).

### Improvements
- **Recent Telegrams show decoded payload** — Each dashboard entry now has a second line with the decoded telegram fields (human-readable enum texts preferred, e.g. `R1: Button BI · EB: pressed`) plus the raw hex data.

## [1.4.0] - 2026-07-04

Field-tested in the Beta channel (issue #2) and confirmed working by users before this stable release.

### New Features
- **D2-05-00 Blind Actuators (NodOn/EnOcean VLD)** — Covers configured with EEP `D2-05-xx` send proper structured VLD (RORG D2) command telegrams instead of simulated F6 rocker presses. This makes **Stop** work (correct 1-byte `Stop` telegram per the EEP spec) and adds a real **Position** slider (0–100 %) in Home Assistant. `Go to Position and Angle` (CMD 1) and `Stop` (CMD 2) are used. Eltako/RPS covers keep the existing F6 rocker-simulation path — the handler branches on the configured EEP. (#2)
- **UTE (bidirectional) teach-in** — NodOn D2-05/D2-01 modules in bidirectional learn mode emit a UTE teach-in query (RORG `0xD4`); the add-on now answers with a proper UTE response while a teach-in session is open, completing pairing. The wizard pre-fills the bound Sender ID and pre-selects the Cover role. (#2)
- **D2-01 switches (e.g. NodOn relay / boiler contact)** — Switch actuators with EEP `D2-01-xx` now receive addressed `Actuator Set Output` VLD commands (`010064` = ON / `010000` = OFF) instead of F6 rocker broadcasts, so they actually switch — and no longer make unrelated D2-05 blinds move via the broadcast. (#2)
- **Reverse direction (invert) option for covers** — Per-device **Invert** flag reverses Open/Close and the position mapping on both the command side and the HA position feedback, for reverse-wired/mounted shutters. Shown in the device form for the Cover role. (#2)

### Bug Fixes
- **Teach-in timeout popup no longer spams** — the 60 s countdown could orphan its `setInterval` and fire the timeout toast every second unstoppably; the countdown now clears itself and re-starting cancels any prior session.
- **Web UI version no longer goes stale** — the displayed version is read from `config.yaml` at runtime (single source of truth via `app_version.py`) instead of being hard-coded, so it can no longer disagree with the store version.

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
