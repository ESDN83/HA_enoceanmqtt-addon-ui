# Changelog

## [2.1.11] - 2026-03-06

### Fixed
- **Kessel Staufix alarm not detected** — All bit offsets in the custom EEP profile were wrong. AL was at offset 0 (DB3.bit7) but should be at offset 29 (DB0.bit2), matching the MV-01-01 profile from ChristopheHD's addon. DI0-DI3 offsets also corrected to standard A5-30-03 positions (23, 22, 21, 20).
  - With data `0100000D`: old offset 0 decoded AL=0 (wrong), correct offset 29 decodes AL=1 (alarm active)
  - DI3 at old offset 7 was reading the condition byte (DB3=0x01), not actual battery status

## [2.1.10] - 2026-03-06

### Fixed
- **Binary sensors still "Unknown" after v2.1.9** — Root cause: cached states were published BEFORE discovery configs on startup. HA evaluated state values with default `payload_on="ON"` before the custom config (`payload_on="1"`) arrived.
  - Refactored startup order: discoveries first, then cached states (with 2s delay)
  - `load_persisted_states()` now only loads into memory; new `republish_cached_states()` publishes after discoveries
  - Fix applies to all scenarios: startup, HA restart (birth message), MQTT reconnect

## [2.1.9] - 2026-03-06

### Fixed
- **Binary sensors showed "Unknown" in HA** — MQTT binary_sensor expects "ON"/"OFF" but EEP values are 0/1. Added `payload_on: "1"` and `payload_off: "0"` to all binary_sensor discovery configs.

## [2.1.8] - 2026-03-06

### Removed
- **Device Model dropdown** removed from device form — hardcoded MODEL_MAPPINGS (MV-01-01, SR65, FSB61NP, FUD61NPN) replaced by Custom EEP Profile ha_mapping system
- `/api/mappings/models` endpoint removed
- Model badge removed from device cards and detail view
- **Mapping priority chain** simplified: Custom EEP ha_mapping → Custom mapping.yaml → Default EEP → Empty

## [2.1.7] - 2026-03-06

### Fixed
- **Bundled ha_mapping not seeded** - existing custom profiles created before ha_mapping support weren't updated because seeding only compared field counts. Now also seeds when bundled profile has ha_mapping that the existing one lacks.

## [2.1.6] - 2026-03-06

### Added - HA Entity Mapping in Custom EEP Profiles
- **HA Mapping Builder** in Custom EEP Profile modal — define how EEP fields map to Home Assistant entities
  - Visual row-based editor: Shortcut, Component, Name, Device Class, Icon, Unit per entity
  - Supports sensor, binary_sensor, switch, light, cover, climate, fan component types
  - Context-aware device class dropdowns (change with component type)
  - Mappings saved alongside profile in custom EEP YAML files
- **Mapping priority chain** updated: Model → Custom EEP ha_mapping → Custom mapping.yaml → Default EEP → Empty
- **Profile detail view** now shows HA entity mapping section with badges
- Users can now create fully custom device profiles including HA discovery without code changes

### Changed
- Custom Profile modal expanded to XL for better HA mapping editing space
- MappingManager now accepts EEPManager reference for ha_mapping lookup

## [2.1.5] - 2026-03-06

### Fixed
- **Custom EEP profiles not loaded** - bundled manufacturer profiles (e.g., Kessel Staufix) were stored in `/app/data/custom_eep/` but EEP manager only searched `/data/custom_eep/`
  - New: Bundled custom profiles are now auto-seeded to persistent storage on startup
  - Auto-update: If bundled profile has more fields than existing, it replaces the outdated one
  - Result: Kessel Staufix A5-30-03 now correctly shows all 5 fields (AL, DI0-DI3) with correct bit offsets

## [2.1.4] - 2026-03-06

### Fixed
- **CRITICAL: Device address lookup was broken** - telegrams from known devices showed as "Unknown device"
  - Root cause: `0x` prefix became `0X` after `.upper()`, causing double-prefix comparison bug
  - Fix: Normalize addresses by stripping `0x`/`0X` prefix before comparison
- **Kessel MV-01-01 model mapping** now exposes all 5 sensors: Alarm (AL), Valve Closed (DI0), Error (DI1), Maintenance Required (DI2), Battery Low (DI3)

## [2.1.2] - 2026-03-06

### Fixed
- **Edit Device** now correctly opens the form instead of "Device Added Successfully!" screen
- Edit form shows "Save Device" button and "Edit Device" heading (instead of "Add Device")
- Device name field is read-only during edit (prevents accidental rename)
- Wizard state properly resets when navigating away from edit form
- **Config Export** button now works (was using GET instead of POST)
- **Delete Device** now removes MQTT discovery entities and sets device offline in HA

## [2.1.1] - 2026-03-06

### Added - Device Model Selection
- **Model dropdown** in device form to select device-specific HA mappings (MV-01-01, SR65, FSB61NP, FUD61NPN)
- **Manufacturer field** in device form
- **Model badge** on device cards and detail view
- **GET /api/mappings/models** endpoint for available model list
- MQTT discovery auto-published on device create and update

### Changed - EEP Profile UI
- Profile tree collapsed by default, custom profiles always expanded at top
- Added Edit and Delete buttons for custom EEP profiles
- Added JavaScript validation for custom profile form (RORG, FUNC, TYPE required)
- Better error messages showing actual server errors

### Fixed
- Custom profile save validation (HTML required attribute doesn't work with onclick buttons)

## [2.1.0] - 2025-03-06

### Changed - ChristopheHD Compatibility
- **MQTT prefix** default changed from `enocean` to `enoceanmqtt` (matches ChristopheHD addon)
- **Discovery UID format** now uses `enocean_{EEP}_{ADDR}_{SHORTCUT}` (address-based, stable)
- **Discovery topic** uses `enocean` node ID: `homeassistant/{component}/enocean/{uid}/config`
- **INI export** uses `sender` field name (was `sender_id`) for ChristopheHD compatibility
- **INI import** reads both `sender` and `sender_id` for backward compatibility
- **Data path** changed from `/config/enocean` to `/data/` (correct HA addon practice)
- Auto-migration of existing config from `/config/enocean` to `/data/` on first startup

### Added - MQTT Architecture
- **LWT (Last Will and Testament)** - gateway publishes offline on unexpected disconnect
- **HA birth message** subscription (`homeassistant/status`) - re-publishes all discoveries when HA restarts
- **Per-device availability** topics (`{prefix}/{device_name}/availability`)
- **Graceful shutdown** publishes offline for all devices before disconnecting
- **MQTT reconnect** automatically re-publishes all discoveries
- QoS 1 for all critical MQTT messages (discovery, availability, commands)

### Fixed
- Discovery configs now use per-device availability instead of global gateway status
- MQTT topic wildcard matching for `#` multi-level wildcard
- Device identifiers use normalized address format (consistent across restarts)

## [2.0.3] - 2025-02-05

### Fixed
- Edit button now opens device edit form instead of "Device Added Successfully" screen
- Unknown Devices list now filters out already-configured devices
- Device cards are clickable and show detail view with recent telegrams and MQTT topics

### Added
- Device detail view with telegram history, MQTT topic info, and device parameters
- Clear button for Recent Telegrams to reset telegram buffer
- Clear also resets Unknown Devices list

## [2.0.2] - 2025-02-02

### Added
- **Cache Device States** option - Persist and restore device states after restart
  - Essential for sensors with infrequent updates (e.g., Kessel Staufix sends every 8-10 hours)
- Mapping versioning with backup rotation (keeps 3 versions)
- Mapping templates for common device types
- Telegram buffer for debugging (last 200 telegrams)
- English translations for configuration options

### Changed
- Simplified configuration - removed TCP host/port options
- Improved HA Ingress compatibility
- Better mobile responsive UI with hamburger menu

### Fixed
- API route ordering for EEP profiles and devices
- UI content hidden behind navbar
- Status indicator not updating correctly

## [2.0.0] - 2025-02-01

### Added
- Complete rewrite as All-in-One addon
- Modern web UI with Bootstrap 5
- Visual device configuration (no YAML editing required)
- EEP profile browser with 50+ profiles from official EEP.xml
- Custom EEP profile editor (EEP Override Editor)
- MQTT mapping configuration
- Home Assistant MQTT Discovery integration
- Teach-in mode for automatic device detection
- Real-time telegram monitoring
- Unknown device detection

### Changed
- Replaced ChristopheHD's addon architecture
- Bundled EEP.xml (no external downloads)
- English-only UI

### Removed
- External EEP.xml download dependency
- Complex YAML configuration files
