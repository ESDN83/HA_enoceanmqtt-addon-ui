# Changelog

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
