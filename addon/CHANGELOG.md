# Changelog

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
