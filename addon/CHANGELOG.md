# Changelog

## [2.1.3] - 2026-03-06

### Fixed
- **Kessel MV-01-01 model mapping** now exposes all 5 sensors: Alarm (AL), Valve Closed (DI0), Error (DI1), Maintenance Required (DI2), Battery Low (DI3)
- Previously only DI0 was mapped, ignoring AL, DI1, DI2, DI3 from the custom EEP profile

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
