# EnOcean MQTT - All-in-One Home Assistant Add-on

[![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https://github.com/ESDN83/HA_enoceanmqtt-addon-ui)

> **⚠️ EARLY RELEASE WARNING**
>
> This is an initial release (v2.0.0) and should be considered **beta software**.
> While functional, there may be bugs or unexpected behavior.
>
> **Please:**
> - **Backup your existing configuration** before installing
> - **Do not use in production** without thorough testing
> - **Report issues and feedback** on [GitHub Issues](https://github.com/ESDN83/HA_enoceanmqtt-addon-ui/issues)
>
> Your feedback is essential to improve this addon!

---

Modern web-based EnOcean to MQTT bridge for Home Assistant with visual device configuration.

**This is an All-in-One solution** - it completely replaces the ChristopheHD enocean-mqtt addon. No separate addon required!

## Features

- **Visual Device Wizard** - Add EnOcean devices via teach-in or manual entry
- **EEP Profile Browser** - Browse all EnOcean Equipment Profiles with detailed field information
- **Custom EEP Profiles** - Create and edit custom profiles for non-standard devices (e.g., Kessel Staufix)
- **MQTT/HA Entity Mapping** - Visual mapping editor for Home Assistant integration
- **Live Telegram Monitor** - Debug incoming EnOcean telegrams in real-time
- **Unknown Device Detection** - Automatically detect and list unconfigured devices
- **Home Assistant MQTT Discovery** - Automatic entity creation in Home Assistant
- **Configuration Export/Import** - Backup and restore your configuration

## Installation

### Via Home Assistant Add-on Store (Recommended)

1. Click the button above or add this repository URL to your Home Assistant Add-on Store:
   ```
   https://github.com/ESDN83/HA_enoceanmqtt-addon-ui
   ```

2. Install the "EnOcean MQTT" add-on

3. Configure the add-on:
   - **Serial Port**: Select your EnOcean USB transceiver (e.g., `/dev/ttyUSB0`)
   - **TCP Port**: Or use TCP connection (format: `tcp:host:port`)

4. Start the add-on and open the Web UI via the sidebar

## Quick Start

1. **Start the add-on** and open the Web UI
2. **Add your first device**:
   - Click "Add Device" in the sidebar
   - Choose "Automatic (Teach-In)" and press the button on your EnOcean device
   - Or enter device details manually
3. **Devices appear automatically** in Home Assistant via MQTT Discovery

## Configuration

### Add-on Options

| Option | Description |
|--------|-------------|
| `serial_port` | Serial port of EnOcean USB transceiver |
| `tcp_port` | TCP connection string (e.g., `tcp:192.168.1.100:9637`) |
| `log_level` | Logging level (debug, info, warning, error) |
| `mqtt.discovery_prefix` | Home Assistant MQTT discovery prefix (default: `homeassistant`) |
| `mqtt.prefix` | MQTT topic prefix for EnOcean devices (default: `enocean`) |
| `mqtt.client_id` | MQTT client identifier |

### Supported EnOcean Profiles

This add-on uses the official EnOcean Alliance EEP.xml containing all standard profiles including:

- **RPS (F6)** - Rocker switches, window handles
- **1BS (D5)** - Single input contacts
- **4BS (A5)** - Temperature, humidity, occupancy, light sensors
- **VLD (D2)** - Electronic switches, dimmers, blinds

### Custom Profiles

Create custom EEP profiles for devices not covered by the official specification:

1. Go to "EEP Profiles" in the web UI
2. Click "Create Custom Profile"
3. Enter RORG, FUNC, TYPE and field definitions
4. Save and use with your devices

An example custom profile for Kessel Staufix is included.

## Web UI

Access the web UI via Home Assistant sidebar (EnOcean icon) or directly at:
```
http://homeassistant.local:8099
```

### Dashboard
- Connection status (MQTT & EnOcean)
- Device and profile counts
- Recent telegram activity
- Unknown device detection with quick-add buttons

### Devices
- List all configured devices
- Add, edit, delete devices
- Search and filter

### EEP Profiles
- Browse profile tree by RORG/FUNC/TYPE
- View field definitions
- Create custom profiles

### Add Device (Teach-In)
- Automatic device detection via teach-in
- Manual entry option
- Profile suggestion based on detected EEP

### Settings
- Export/Import configuration
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
| `/api/mappings` | GET | Get all mappings |
| `/api/mappings/{eep_id}` | PUT | Update mapping |
| `/api/system/status` | GET | System status |
| `/api/system/export` | POST | Export config (ZIP) |
| `/api/system/import` | POST | Import config |
| `/api/system/restart` | POST | Restart services |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Web UI (Bootstrap 5)               │
├─────────────────────────────────────────────────────┤
│                  FastAPI REST API                    │
├─────────────────────────────────────────────────────┤
│  EEPManager │ DeviceManager │ MappingManager        │
│  MQTTHandler │ SerialHandler │ TelegramBuffer       │
├─────────────────────────────────────────────────────┤
│        EnOcean USB300/TCM515     │     MQTT Broker  │
└─────────────────────────────────────────────────────┘
```

## Migration from ChristopheHD addon

If you're migrating from the ChristopheHD enocean-mqtt addon:

1. **Export your config** from the old addon (if possible)
2. **Install this addon** and stop the old one
3. **Import your devices** via the Settings page or manually re-add them
4. Your existing `enoceanmqtt.devices` file format is supported for import

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

### Teach-In Not Working
- Ensure EnOcean gateway is connected (green status)
- Press the teach-in button firmly on the device
- Some devices require multiple presses

## Support

- Report issues on [GitHub Issues](https://github.com/ESDN83/HA_enoceanmqtt-addon-ui/issues)
- Check logs in Home Assistant: Settings > Add-ons > EnOcean MQTT > Log

## Credits

- EnOcean Alliance for the EEP specification
- Home Assistant community

## License

MIT License - see LICENSE file

---

**Note**: This addon is not affiliated with EnOcean Alliance or Home Assistant. It is a community project to improve the EnOcean integration experience.
