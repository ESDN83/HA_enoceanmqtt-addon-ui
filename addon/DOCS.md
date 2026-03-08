# EnOcean MQTT

![Dashboard](https://raw.githubusercontent.com/ESDN83/HA_enoceanmqtt-addon-ui/main/images/screenshot-dashboard.png)

All-in-One EnOcean to MQTT bridge with a modern web UI for Home Assistant.

This add-on replaces the need for separate EnOcean bridges and YAML configuration.
Add your EnOcean devices visually, browse EEP profiles, and manage MQTT mappings -
all from within Home Assistant.

## Key Features

- **Visual Device Management** - Add, edit and remove EnOcean devices through a web UI
- **Teach-In Mode** - Automatic device detection when pressing the learn button
- **56+ EEP Profiles** - Built-in EnOcean Equipment Profile browser
- **Custom Profiles** - Create profiles for non-standard devices (e.g., Kessel Staufix)
- **MQTT Discovery** - Devices appear automatically in Home Assistant
- **Live Telegram Monitor** - Debug incoming EnOcean telegrams in real-time
- **Unknown Device Detection** - Detect and quick-add unconfigured devices
- **State Persistence** - Restore device states after restart (important for sensors with infrequent updates)
- **Dark Mode** - Automatic light/dark theme based on your Home Assistant settings
- **Mobile Friendly** - Responsive UI with sidebar navigation

## Supported Hardware

- **EnOcean USB300** USB transceiver
- **EnOcean TCM515** USB transceiver
- Any serial-based EnOcean transceiver module

## Supported EnOcean Profiles

| RORG | Type | Examples |
|------|------|----------|
| **RPS (F6)** | Rocker switches | Wall switches, window handles |
| **1BS (D5)** | Single contacts | Door/window contacts |
| **4BS (A5)** | Sensors & actuators | Temperature, humidity, occupancy, light, dimmers (A5-38-08) |
| **VLD (D2)** | Variable length | Electronic switches, blinds, metering |

## Quick Start

1. **Configure** your EnOcean USB serial port in the add-on settings
2. **Start** the add-on and open the Web UI via the sidebar
3. **Add a device**: Click "Add Device", choose Teach-In, and press the learn button on your EnOcean device
4. **Done** - The device appears automatically in Home Assistant via MQTT Discovery

## Configuration

### Serial Port

Select your EnOcean USB transceiver from the dropdown. Common ports:
- `/dev/ttyUSB0` (USB300)
- `/dev/ttyAMA0` (Raspberry Pi GPIO)

### MQTT Settings

The add-on automatically connects to Home Assistant's MQTT broker (Mosquitto).

| Option | Default | Description |
|--------|---------|-------------|
| **Discovery Prefix** | `homeassistant` | MQTT discovery prefix for HA auto-detection |
| **Topic Prefix** | `enocean` | Topics are created as `enocean/{device}/state` |
| **Client ID** | `enocean_gateway` | Unique MQTT client identifier |

### Cache Device States

When enabled (default), the add-on persists the last known state of all devices.
After a restart, these states are republished so that infrequent sensors (like a
Kessel Staufix that only reports every 8-10 hours) don't show as "unavailable".

## Web UI Sections

### Dashboard
Overview with connection status, device counts, recent telegrams and unknown device detection.

![Dashboard](https://raw.githubusercontent.com/ESDN83/HA_enoceanmqtt-addon-ui/main/images/screenshot-dashboard.png)

### Devices
List and manage all configured EnOcean devices. Add, edit, or remove devices.

![Devices](https://raw.githubusercontent.com/ESDN83/HA_enoceanmqtt-addon-ui/main/images/screenshot-devices.png)

### EEP Profiles
Browse the complete EnOcean Equipment Profile tree. View field definitions and
create custom profiles for unsupported devices.

![EEP Profiles](https://raw.githubusercontent.com/ESDN83/HA_enoceanmqtt-addon-ui/main/images/screenshot-profiles.png)

### Entity Mappings
Define how EEP profile fields map to Home Assistant entities (sensor, binary_sensor,
switch, light, cover, etc.).

### Add Device
Wizard for adding new devices via Teach-In (automatic) or manual entry.

### Settings
Export/import configuration, upload custom EEP.xml, view system information, restart services.

![Settings](https://raw.githubusercontent.com/ESDN83/HA_enoceanmqtt-addon-ui/main/images/screenshot-settings.png)

## Migration from ChristopheHD Addon

If you are migrating from the ChristopheHD enocean-mqtt addon:

1. Export your config from the old addon (if possible)
2. Install this addon and stop the old one
3. Import your devices via the Settings page
4. The old `enoceanmqtt.devices` file format is supported for import

## Troubleshooting

### EnOcean Gateway Not Connecting
- Verify the correct serial port is selected in the addon settings
- Check that no other addon is using the same serial port
- Try unplugging and reconnecting the USB transceiver

### Devices Not Appearing in Home Assistant
- Check that MQTT is connected (green badge in the Web UI)
- Verify the MQTT discovery prefix matches your HA config (default: `homeassistant`)
- Check the addon log for errors

### Teach-In Not Working
- Make sure the EnOcean gateway shows "connected" (green status)
- Press the teach-in button firmly on your device
- Some devices require multiple presses or holding the button

## Support

- Report issues on [GitHub](https://github.com/ESDN83/HA_enoceanmqtt-addon-ui/issues)
- Check logs in Home Assistant: Settings > Add-ons > EnOcean MQTT > Log
