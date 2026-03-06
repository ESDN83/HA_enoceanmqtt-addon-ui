# EnOcean MQTT - All-in-One Home Assistant Add-on

[\![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https://github.com/ESDN83/HA_enoceanmqtt-addon-ui)

Modern web-based EnOcean to MQTT bridge for Home Assistant with visual device configuration.

**This is an All-in-One solution**

<img width="2235" height="1291" alt="grafik" src="https://github.com/user-attachments/assets/19cb1b4a-0545-4235-b29b-b5bc4fba81b8" />

## Features

- **Visual Device Wizard** - Add EnOcean devices via teach-in or manual entry
- **EEP Profile Browser** - Browse 96+ EnOcean Equipment Profiles with detailed field information
- **Custom EEP Profiles** - Create and edit custom profiles for non-standard devices, with built-in HA Entity Mapping
- **Home Assistant MQTT Discovery** - Automatic entity creation in Home Assistant
- **Live Telegram Monitor** - Debug incoming EnOcean telegrams in real-time
- **Unknown Device Detection** - Automatically detect and list unconfigured devices
- **Configuration Export/Import** - Backup and restore your configuration as ZIP files
- **Device State Caching** - Persist sensor states across restarts (essential for infrequent senders)
- **Actuator Control** - Control Eltako dimmers, switches, and blinds via F6 rocker telegrams with teach-in support

## Installation

### Via Home Assistant Add-on Store (Recommended)

1. Click the button above or add this repository URL to your Home Assistant Add-on Store:
   ```
   https://github.com/ESDN83/HA_enoceanmqtt-addon-ui
   ```

2. Install the "EnOcean MQTT" add-on

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

- **RPS (F6)** - Rocker switches, window handles
- **1BS (D5)** - Single input contacts
- **4BS (A5)** - Temperature, humidity, occupancy, light sensors
- **VLD (D2)** - Electronic switches, dimmers, blinds
- **MSC (D1)** - Manufacturer-specific devices

### Custom EEP Profiles

Create custom EEP profiles for devices not covered by the official specification:

1. Go to "EEP Profiles" in the web UI
2. Click "Create Custom Profile"
3. Enter RORG, FUNC, TYPE and define data fields (shortcut, offset, size)
4. Add HA Entity Mappings to control how fields appear in Home Assistant
5. Save and assign the profile to your devices

## Custom EEP Profile Guide

This guide explains how to create Custom EEP Profiles with real-world examples. A link to this guide is also available directly in the "Create Custom Profile" dialog.

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
<img width="1705" height="1702" alt="grafik" src="https://github.com/user-attachments/assets/8df696e5-04d0-4207-929e-6f19142b9a55" />



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

### Tips

- **Find bit offsets**: Check the [EnOcean EEP Viewer](https://www.enocean-alliance.org/eep/) or the manufacturer documentation
- **Test with Live Telegrams**: Use the Dashboard > Recent Telegrams view to see raw data bytes, then map bits to fields
- **Enum values**: For binary fields (size=1), use values `"0"` and `"1"`
- **HA Device Classes**: Common classes: `temperature`, `humidity`, `safety`, `problem`, `motion`, `door`, `window`, `battery`
- **Override standard profiles**: Create a custom profile with the same RORG-FUNC-TYPE as a built-in profile to override it

## Usage Examples

### Backup & Restore

**Export:**
1. Go to "Settings" in the web UI
2. Click "Export Configuration" - downloads a ZIP file containing:
   - `devices.json` (all configured devices)
   - `mapping.yaml` (custom entity mappings)
   - `custom_eep/*.yaml` (custom EEP profiles)

**Import / Restore:**
1. Go to "Settings" > "Import Configuration"
2. Upload the ZIP file
3. Devices and profiles are restored automatically

### Controlling Actuators (Eltako Dimmers/Switches/Blinds)

1. **Read Base ID** — Go to Teach-In and click "Read" to get the gateway's base address
2. **Put actuator in learn mode** — Short press the learn button on the Eltako device (LED blinks). For FD62NPN dimmers: press rotary knob 4× short + 1× long (>2s) — lamp flickers to confirm
3. **Send teach-in** — Enter actuator address, choose a unique sender offset (1-127), click "Send Teach-In"
4. **Add the device** — Use "Manual Entry" with the sender ID, set Device Role to light/switch/cover
5. **Test from UI** — Open device detail and use the Test ON/OFF buttons
6. **Control from HA** — The device appears as a light/switch/cover entity in Home Assistant

**Tip:** To clear all learned senders from an Eltako actuator, press the learn button 5 times quickly.

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

### Devices
- List all configured devices with EEP info
- Add, edit, delete devices
- View device detail with recent telegrams and MQTT topics

### EEP Profiles
- Browse profile tree by RORG/FUNC/TYPE
- View field definitions with bit offsets
- Create custom profiles with HA entity mapping

### Teach-In
- Automatic device detection via teach-in mode
- Manual entry option
- Profile suggestion based on detected EEP

### Settings
- Export/Import configuration (ZIP)
- Restart services

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
| `/api/system/status` | GET | System status |
| `/api/system/export` | POST | Export config (ZIP) |
| `/api/system/import` | POST | Import config |
| `/api/system/restart` | POST | Restart services |

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
5. MQTT topics are compatible - existing HA entities should continue working

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
- The EEP profile may not match your device - try creating a Custom EEP Profile
- Check bit offsets and field sizes match your device documentation

### Teach-In Not Working
- Ensure EnOcean gateway is connected (green status)
- Press the teach-in button firmly on the device
- Some devices require multiple presses

## Support

- Report issues on [GitHub Issues](https://github.com/ESDN83/HA_enoceanmqtt-addon-ui/issues)
- Check logs in Home Assistant: Settings > Add-ons > EnOcean MQTT > Log

## Credits

- [ChristopheHD](https://github.com/ChristopheHD/enocean) - EEP.xml profile database and MQTT compatibility patterns
- EnOcean Alliance for the EEP specification
- Home Assistant community

## License

MIT License - see LICENSE file

---

**Note**: This addon is not affiliated with EnOcean Alliance or Home Assistant. It is a community project to improve the EnOcean integration experience.
