# EnOcean MQTT UI - All-in-One Home Assistant Add-on

[![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https://github.com/ESDN83/HA_enoceanmqtt-addon-ui)

Modern web-based EnOcean to MQTT bridge for Home Assistant with visual device configuration.

**This is an All-in-One solution** — it completely replaces the ChristopheHD enocean-mqtt addon. No separate addon required!

<img width="1492" height="874" alt="EnOcean MQTT Dashboard" src="https://github.com/user-attachments/assets/6cc73258-3848-4ee0-9aef-250efa3b9080" />

## Features

- **Visual Device Wizard** — Add EnOcean devices via teach-in or manual entry
- **EEP Profile Browser** — Browse 96+ EnOcean Equipment Profiles with detailed field information
- **Custom EEP Profiles** — Create and edit custom profiles for non-standard devices, with built-in HA Entity Mapping
- **HA Entity Mapping Editor** — Visual editor with advanced MQTT discovery fields (state_class, expire_after, entity_category, force_update, etc.) plus YAML text mode for power users
- **EEP.xml Upload** — Upload your own EEP.xml profile database or use the bundled one
- **Home Assistant MQTT Discovery** — Automatic entity creation in Home Assistant
- **Live Telegram Monitor** — Debug incoming EnOcean telegrams in real-time
- **Unknown Device Detection** — Automatically detect and list unconfigured devices
- **Configuration Export/Import** — Backup and restore your configuration as ZIP files
- **Local Backup System** — Create, list, restore, and delete local backups with confirmation dialogs
- **Device State Caching** — Persist sensor states across restarts (essential for infrequent senders)
- **Actuator Control** — Control Eltako dimmers, switches, and blinds via F6 rocker telegrams with teach-in support
- **Dark Mode** — Automatically adapts to Home Assistant theme (dark/light) and OS preference
- **Multi-Language UI** — Auto-detects browser language, supports 11 languages (EN, DE, ZH, HI, ES, FR, AR, BN, PT, RU, JA)

## Installation

### Via Home Assistant Add-on Store (Recommended)

1. Click the button above or add this repository URL to your Home Assistant Add-on Store:
   ```
   https://github.com/ESDN83/HA_enoceanmqtt-addon-ui
   ```

2. Install the "EnOcean MQTT UI" add-on

3. Configure the add-on:
   - **Serial Port**: Select your EnOcean USB transceiver (e.g., `/dev/ttyUSB0` or TCP: `tcp:192.168.1.100:9637`)

4. Start the add-on and open the Web UI via the sidebar

## Quick Start

1. **Start the add-on** and open the Web UI
2. **Add your first device**:
   - Click "Add Device" in the sidebar
   - Choose "Automatic (Teach-In)" and press the button on your EnOcean device
   - Or enter device details manually (address, EEP profile)
3. **Devices appear automatically** in Home Assistant via MQTT Discovery

## Configuration

### Add-on Options

| Option | Description |
|--------|-------------|
| `serial_port` | Serial port of EnOcean USB transceiver (e.g., `/dev/ttyUSB0` or `tcp:host:port`) |
| `log_level` | Logging level (debug, info, warning, error) |
| `cache_device_states` | Persist device states across restarts (default: true) |
| `mqtt.discovery_prefix` | Home Assistant MQTT discovery prefix (default: `homeassistant`) |
| `mqtt.prefix` | MQTT topic prefix for EnOcean devices (default: `enoceanmqtt`) |
| `mqtt.client_id` | MQTT client identifier |

### Supported EnOcean Profiles

This add-on bundles the EnOcean EEP.xml (sourced from [ChristopheHD's enocean library](https://github.com/ChristopheHD/enocean)) containing 96+ standard profiles including:

- **RPS (F6)** — Rocker switches, window handles
- **1BS (D5)** — Single input contacts
- **4BS (A5)** — Temperature, humidity, occupancy, light sensors
- **VLD (D2)** — Electronic switches, dimmers, blinds
- **MSC (D1)** — Manufacturer-specific devices

You can also upload your own EEP.xml via the Settings page.

### Custom EEP Profiles

Create custom EEP profiles for devices not covered by the official specification:

1. Go to "EEP Profiles" in the web UI
2. Click "Create Custom Profile"
3. Enter RORG, FUNC, TYPE and define data fields (shortcut, offset, size)
4. Add HA Entity Mappings to control how fields appear in Home Assistant
5. Save and assign the profile to your devices

## Custom EEP Profile Guide

This guide explains how to create Custom EEP Profiles with real-world examples.

### Understanding EnOcean Telegram Data

EnOcean 4BS (A5) telegrams carry 4 data bytes (DB3, DB2, DB1, DB0 = 32 bits). The **offset** is the bit position counted from the MSB of DB3:

```
Byte:    DB3 (byte 0)     DB2 (byte 1)     DB1 (byte 2)     DB0 (byte 3)
Bits:    7 6 5 4 3 2 1 0  7 6 5 4 3 2 1 0  7 6 5 4 3 2 1 0  7 6 5 4 3 2 1 0
Offset:  0 1 2 3 4 5 6 7  8 9 ...                             ... 29 30 31
```

So **offset 29** = DB0, bit 2. **Offset 0** = DB3, bit 7.

### Field Types

| Type | Use Case | Example |
|------|----------|---------|
| `enum` | On/off, states, named values | Alarm (0=off, 1=on) |
| `value` | Scaled numbers (temperature, humidity) | Temperature 0-40°C from raw 255-0 |
| `command` | Multi-value commands | Operating mode selection |

### Example 1: Binary Alarm Sensor (Kessel Staufix A5-30-03)

The Kessel Staufix backwater valve sends a single alarm bit. Telegram data `0100000D` means alarm active.

**Telegram Fields (JSON):**
```json
[
  {
    "shortcut": "AL",
    "description": "Alarm",
    "offset": 29,
    "size": 1,
    "type": "enum",
    "values": [
      {"value": "0", "description": "No alarm"},
      {"value": "1", "description": "Alarm active"}
    ]
  }
]
```

<img width="1702" height="1702" alt="grafik" src="https://github.com/user-attachments/assets/d2c36df6-dab5-422f-870d-434a4333fe0e" />

**HA Entity Mapping:**

| Shortcut | Component | Name | Device Class | Icon |
|----------|-----------|------|-------------|------|
| AL | binary_sensor | Alarm | safety | mdi:water-alert |

**Add Device:** Name `Staufix`, Address `0x05834FA4`, EEP `A5-30-03`

Result: A binary sensor in HA that shows alarm status.

### Example 2: Temperature & Humidity Sensor (A5-04-01)

A sensor sending temperature (0-40°C) and humidity (0-100%) in 4 bytes.

**Telegram Fields (JSON):**
```json
[
  {
    "shortcut": "HUM",
    "description": "Humidity",
    "offset": 8,
    "size": 8,
    "type": "value",
    "unit": "%",
    "min": 0, "max": 250,
    "scale_min": 0, "scale_max": 100
  },
  {
    "shortcut": "TMP",
    "description": "Temperature",
    "offset": 16,
    "size": 8,
    "type": "value",
    "unit": "°C",
    "min": 0, "max": 250,
    "scale_min": 0, "scale_max": 40
  }
]
```

- `min`/`max` = raw value range from the telegram bits
- `scale_min`/`scale_max` = real-world unit range

**HA Entity Mapping:**

| Shortcut | Component | Name | Device Class | Unit | Icon |
|----------|-----------|------|-------------|------|------|
| HUM | sensor | Humidity | humidity | % | mdi:water-percent |
| TMP | sensor | Temperature | temperature | °C | mdi:thermometer |

### Example 3: Rocker Switch with Multiple States (F6-02-01)

A rocker switch sends button press events as enum values.

**Telegram Fields (JSON):**
```json
[
  {
    "shortcut": "R1",
    "description": "Rocker 1st action",
    "offset": 0,
    "size": 3,
    "type": "enum",
    "values": [
      {"value": "0", "description": "Button AI"},
      {"value": "1", "description": "Button A0"},
      {"value": "2", "description": "Button BI"},
      {"value": "3", "description": "Button B0"}
    ]
  },
  {
    "shortcut": "EB",
    "description": "Energy Bow",
    "offset": 4,
    "size": 1,
    "type": "enum",
    "values": [
      {"value": "0", "description": "Released"},
      {"value": "1", "description": "Pressed"}
    ]
  }
]
```

### HA Entity Mapping — Advanced Fields

The mapping editor supports all MQTT discovery fields for Home Assistant. In addition to the basic fields (Component, Name, Device Class, Icon, Unit), each mapping row has a collapsible **Advanced** section:

| Field | Description | Example |
|-------|-------------|---------|
| `state_class` | HA statistics classification | `measurement`, `total`, `total_increasing` |
| `entity_category` | HA entity category | `diagnostic`, `config` |
| `expire_after` | Seconds after which the sensor value expires | `3600` (1 hour) |
| `force_update` | Fire state update even if value unchanged | `true` |
| `suggested_display_precision` | Decimal places in HA UI | `1` |
| `value_template` | Custom Jinja2 template for value extraction | `{{ value_json.TMP }}` |

**Text Mode:** Click the "Text Mode" button to switch to a YAML editor where you can set any MQTT discovery field, including fields not available in the visual editor. The YAML text mode supports round-trip editing (Visual → Text → Visual).

### Tips

- **Find bit offsets**: Check the [EnOcean EEP Viewer](https://www.enocean-alliance.org/eep/) or the manufacturer documentation
- **Test with Live Telegrams**: Use the Dashboard > Recent Telegrams view to see raw data bytes, then map bits to fields
- **Enum values**: For binary fields (size=1), use values `"0"` and `"1"`
- **HA Device Classes**: Common classes: `temperature`, `humidity`, `safety`, `problem`, `motion`, `door`, `window`, `battery`
- **Override standard profiles**: Create a custom profile with the same RORG-FUNC-TYPE as a built-in profile to override it
- **Override standard mappings**: Use the inline mapping editor on any standard EEP profile to customize how fields map to HA entities

## Usage Examples

### Backup & Restore

**Export (download):**
1. Go to "Settings" in the web UI
2. Click "Export All" — downloads a ZIP file containing devices, mappings, and custom profiles

**Local Backup:**
1. Go to "Settings" > "Local Backups"
2. Click "Create Backup" — saves a ZIP to the addon's data directory
3. The backup list shows all local backups with date, size, and device count
4. Use the download, restore, or delete buttons per backup
5. Restore and delete actions require confirmation via popup dialog

**Import:**
1. Go to "Settings" > click "Import"
2. Upload a ZIP file (from Export or Local Backup download)
3. Devices, mappings, custom profiles, and custom EEP.xml are restored automatically

### Controlling Actuators (Eltako Dimmers/Switches/Blinds)

1. **Read Base ID** — Go to Teach-In and click "Read" to get the gateway's base address
2. **Put actuator in learn mode** — Short press the learn button on the Eltako device (LED blinks). For FD62NPN dimmers: press rotary knob 4x short + 1x long (>2s) — lamp flickers to confirm
3. **Send teach-in** — Enter actuator address, choose a unique sender offset (1-127), click "Send Teach-In"
4. **Add the device** — Use "Manual Entry" with the sender ID, set Device Role to light/switch/cover
5. **Test from UI** — Open device detail and use the Test ON/OFF buttons
6. **Control from HA** — The device appears as a light/switch/cover entity in Home Assistant

**Tip:** To clear all learned senders from an Eltako actuator, press the learn button 5 times quickly.

### EEP.xml Management

You can upload a custom EEP.xml file to replace the bundled profile database:

1. Go to "Settings" > "EEP.xml Profile Database"
2. Click "Upload EEP.xml" and select your XML file
3. The file is validated and profiles are reloaded immediately
4. To revert, click "Delete Custom" to fall back to the bundled EEP.xml

Custom EEP.xml files are included in backup exports and restored on import.

### MQTT Topics

With the default prefix `enoceanmqtt`, each device publishes to:

```
enoceanmqtt/<device_name>/state         - device state (JSON, retained)
enoceanmqtt/<device_name>/set           - commands (for actuators)
enoceanmqtt/<device_name>/availability  - online/offline
```

Discovery configs are published to:
```
homeassistant/<component>/enocean/<uid>/config
```

## Web UI

Access the web UI via Home Assistant sidebar (EnOcean icon).

### Dashboard
- Connection status (MQTT & EnOcean)
- Device and profile counts
- Recent telegram activity
- Unknown device detection with quick-add buttons

<img width="1492" height="874" alt="Dashboard" src="https://github.com/user-attachments/assets/6cc73258-3848-4ee0-9aef-250efa3b9080" />

### Devices
- List all configured devices with EEP info
- Add, edit, delete devices
- View device detail with recent telegrams and MQTT topics

<img width="1492" height="874" alt="Devices" src="https://github.com/user-attachments/assets/0e7981a0-9db0-4e63-9bd1-2bd4d20c5c85" />

### EEP Profiles
- Browse profile tree by RORG/FUNC/TYPE
- View field definitions with bit offsets
- Create custom profiles with HA entity mapping

<img width="1492" height="874" alt="EEP Profiles" src="https://github.com/user-attachments/assets/ca0c5baa-4566-45bb-8150-79c77ca3c48e" />

### Teach-In
- Automatic device detection via teach-in mode
- Manual entry option
- Profile suggestion based on detected EEP

### Settings
- Export/Import configuration (ZIP download/upload)
- Local Backup: create, list, restore, delete (with confirmation popups)
- EEP.xml management: upload custom, view source info, delete to revert
- Restart services

<img width="1492" height="874" alt="Settings" src="https://github.com/user-attachments/assets/370072b1-7219-4566-a733-2c9e58b018fa" />

## API Reference

The add-on provides a REST API for automation:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/devices` | GET | List all devices |
| `/api/devices` | POST | Create device |
| `/api/devices/{name}` | PUT | Update device |
| `/api/devices/{name}` | DELETE | Delete device |
| `/api/eep` | GET | List all EEP profiles |
| `/api/eep/{eep_id}` | GET | Get profile details |
| `/api/eep/tree` | GET | Get profiles as tree |
| `/api/eep/custom` | POST | Create custom profile |
| `/api/gateway/recent-telegrams` | GET | Get recent telegrams |
| `/api/gateway/unknown-devices` | GET | List unknown devices |
| `/api/gateway/teach-in` | WebSocket | Teach-in mode |
| `/api/gateway/teach-in-actuator` | POST | Send teach-in to actuator |
| `/api/gateway/test-actuator` | POST | Test actuator ON/OFF/Open/Close |
| `/api/gateway/info` | GET | Gateway info (base ID, port) |
| `/api/mappings` | GET | Get all mappings |
| `/api/mappings/{eep_id}` | PUT | Update mapping |
| `/api/system/status` | GET | System status |
| `/api/system/eep-info` | GET | EEP.xml source info |
| `/api/system/upload-eep` | POST | Upload custom EEP.xml |
| `/api/system/delete-eep` | DELETE | Delete custom EEP.xml |
| `/api/system/export` | POST | Export config (ZIP download) |
| `/api/system/import` | POST | Import config (ZIP upload) |
| `/api/system/backup` | POST | Create local backup |
| `/api/system/backups` | GET | List local backups |
| `/api/system/backup/restore/{filename}` | POST | Restore from backup |
| `/api/system/backup/{filename}` | DELETE | Delete backup |
| `/api/system/backup/download/{filename}` | GET | Download backup |
| `/api/system/restart` | POST | Restart services |

## Configuration Files

All configuration files are stored in YAML format in the addon's `/data` directory:

| File | Description |
|------|-------------|
| `devices.yaml` | Device list with addresses, EEP profiles, and settings |
| `mapping.yaml` | Custom EEP-to-HA entity mappings |
| `mapping_overrides.yaml` | Per-profile mapping overrides from the inline editor |
| `last_states.yaml` | Cached device states for persistence across restarts |
| `custom_eep/*.yaml` | Custom EEP profile definitions |
| `enoceanmqtt.devices` | Legacy INI format (auto-generated for enocean-mqtt compatibility) |
| `EEP.xml` | Optional user-uploaded EEP profile database |

The `mapping_overrides.yaml` and `mapping.yaml` files can be edited manually if needed. Changes take effect after restarting the addon.

**Backup format:** Export and backup ZIP files contain YAML files. Old backups with JSON files (from versions before 1.2.0) are automatically converted on import/restore.

## Architecture

```
+---------------------------------------------------------+
|                   Web UI (Bootstrap 5)                   |
+---------------------------------------------------------+
|                  FastAPI REST API                        |
+---------------------------------------------------------+
|  EEPManager | DeviceManager | MappingManager            |
|  MQTTHandler | SerialHandler | TelegramBuffer           |
+---------------------------------------------------------+
|        EnOcean USB300/TCM515     |     MQTT Broker       |
+---------------------------------------------------------+
```

## Migration from ChristopheHD addon

If you are migrating from the ChristopheHD enocean-mqtt addon:

1. **Export your config** from the old addon (if possible)
2. **Install this addon** and stop the old one
3. **Import your devices** via the Settings page or manually re-add them
4. Your existing `enoceanmqtt.devices` file format is supported for import
5. MQTT topics are compatible — existing HA entities should continue working

## Development

### Local Development

```bash
cd addon/rootfs/app
pip install -r requirements.txt
export CONFIG_PATH=./test_config
python main.py
```

Access at `http://localhost:8099`

### Building the Add-on

```bash
cd addon
docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18 -t enocean-mqtt .
```

## Troubleshooting

### EnOcean Gateway Not Connecting
- Verify the correct serial port is selected
- Check USB device permissions
- Try unplugging and reconnecting the USB transceiver

### MQTT Not Connected
- Ensure MQTT broker is running
- Check MQTT credentials in Home Assistant
- Verify mosquitto or similar MQTT broker addon is installed

### Devices Not Appearing in Home Assistant
- Check MQTT Discovery is enabled in HA
- Verify the `homeassistant` prefix matches your MQTT configuration
- Check the addon logs for errors

### Sensors Show Wrong Values
- The EEP profile may not match your device — try creating a Custom EEP Profile
- Check bit offsets and field sizes match your device documentation

### Teach-In Not Working
- Ensure EnOcean gateway is connected (green status)
- Press the teach-in button firmly on the device
- Some devices require multiple presses

## Support

- Report issues on [GitHub Issues](https://github.com/ESDN83/HA_enoceanmqtt-addon-ui/issues)
- Check logs in Home Assistant: Settings > Add-ons > EnOcean MQTT UI > Log

## Credits

- [ChristopheHD](https://github.com/ChristopheHD/enocean) — EEP.xml profile database and MQTT compatibility patterns
- EnOcean Alliance for the EEP specification
- Home Assistant community

## License

MIT License - see LICENSE file

---

**Note**: This addon is not affiliated with EnOcean Alliance or Home Assistant. It is a community project to improve the EnOcean integration experience.
