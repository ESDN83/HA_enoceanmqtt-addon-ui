# Changelog

## [2.0.1] - 2024-01-XX

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

## [2.0.0] - 2024-01-XX

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
