# EnOcean MQTT - All-in-One Home Assistant Add-on

[\![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https://github.com/ESDN83/HA_enoceanmqtt-addon-ui)

Modern web-based EnOcean to MQTT bridge for Home Assistant with visual device configuration.

**This is an All-in-One solution** - it completely replaces the ChristopheHD enocean-mqtt addon. No separate addon required\!

## Features

- **Visual Device Wizard** - Add EnOcean devices via teach-in or manual entry
- **EEP Profile Browser** - Browse 96+ EnOcean Equipment Profiles with detailed field information
- **Custom EEP Profiles** - Create and edit custom profiles for non-standard devices, with built-in HA Entity Mapping
- **Home Assistant MQTT Discovery** - Automatic entity creation in Home Assistant
- **Live Telegram Monitor** - Debug incoming EnOcean telegrams in real-time
- **Unknown Device Detection** - Automatically detect and list unconfigured devices
- **Configuration Export/Import** - Backup and restore your configuration as ZIP files
- **Device State Caching** - Persist sensor states across restarts (essential for infrequent senders)

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

## Usage Examples

### Example 1: Adding a Kessel Staufix (A5-30-03)

The Kessel Staufix backwater valve reports its alarm status via the A5-30-03 EEP profile. Since it uses a manufacturer-specific interpretation, you need a Custom EEP Profile:

1. **Create Custom Profile** in "EEP Profiles" > "Create Custom Profile":
   - RORG: `A5`, FUNC: `30`, TYPE: `03`
   - Description: `Kessel Staufix Backwater Alarm`
   - Add field: Shortcut `AL`, Offset `29`, Size `1` (Alarm bit at DB0.bit2)

2. **Add HA Mapping** in the same profile:
   - Shortcut: `AL`
   - Component: `binary_sensor`
   - Device Class: `problem`
   - Name: `Alarm`

3. **Add Device** > Manual Entry:
   - Name: `Staufix`
   - Address: your device address (e.g., `0x05834FA4`)
   - EEP: `A5-30-03`

4. The device appears in Home Assistant as a binary sensor showing alarm status.

### Example 2: Backup & Restore

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

### Example 3: Understanding MQTT Topics

With the default prefix `enoceanmqtt`, each device publishes to:

```
enoceanmqtt/<device_name>/<shortcut>    - sensor value
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
