# HA_enoceanmqtt-addon-ui

[![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https://github.com/ESDN83/HA_enoceanmqtt-addon-ui)

A comprehensive Home Assistant addon that provides a user-friendly web-based interface for configuring the HA_enoceanmqtt addon. This tool eliminates the need for manual YAML editing by offering visual editors for EnOcean device configurations and MQTT mappings.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

The HA_enoceanmqtt-addon-ui is designed to simplify the complex process of configuring EnOcean devices in Home Assistant. EnOcean technology uses wireless sensors and actuators that communicate via radio telegrams. The HA_enoceanmqtt addon bridges these devices to Home Assistant via MQTT, but configuring it requires understanding EEP (EnOcean Equipment Profile) specifications and manual YAML file editing.

This UI addon provides:
- Visual exploration of EEP profiles
- Form-based device configuration
- Drag-and-drop MQTT mapping creation
- Configuration validation and testing
- Pre-built templates for common devices

## Features

### EEP Browser
- **Searchable Database**: Browse all available EnOcean Equipment Profiles (EEPs) from the official EnOcean Alliance XML database.
- **Detailed Information**: View RORG, FUNC, TYPE, descriptions, and telegram structures for each EEP.
- **Real-time Search**: Filter EEPs by keywords, RORG, or device type.

### Device Editor
- **Form-Based Input**: Easy-to-use forms for device parameters (address, RORG, FUNC, TYPE, sender ID).
- **Hex Validation**: Automatic validation of hexadecimal addresses and codes.
- **Device Management**: Add, edit, and delete device configurations.
- **Import/Export**: Load existing `enoceanmqtt.devices` files for editing.

### Mapping Editor
- **Visual Mapping**: Link EEP telegram fields to Home Assistant entities (sensors, switches, lights).
- **MQTT Discovery**: Generate proper MQTT discovery payloads for automatic HA entity creation.
- **JSON Editor**: Direct editing of mapping.yaml with syntax highlighting and validation.

### Validation Tools
- **YAML Syntax Check**: Validate configuration file syntax.
- **EEP Compatibility**: Ensure device configurations match selected EEPs.
- **Telegram Simulation**: Test configurations with simulated EnOcean telegrams.

### Wizards
- **Device Templates**: Pre-configured setups for popular devices:
  - Eltako TF61J Jalousie Actor (A5-3F-7F)
  - Kessel Stauffix Valve (A5-20-04)
- **Quick Setup**: Fill forms with template data and customize as needed.

### Export/Import
- **File Generation**: Download configured `enoceanmqtt.devices` and `mapping.yaml` files.
- **Backup/Restore**: Import existing configurations for modification.

## Prerequisites

- Home Assistant (2023+ recommended)
- HA_enoceanmqtt addon installed and configured
- USB300 EnOcean gateway or compatible hardware
- Basic understanding of EnOcean concepts (optional, as the UI guides you)

## Installation

### Method 1: Via Home Assistant Add-on Store

1. In Home Assistant, go to **Settings** > **Add-ons** > **Add-on Store**.
2. Click the menu (three dots) and select **Repositories**.
3. Add repository: `https://github.com/ESDN83/HA_enoceanmqtt-addon-ui`
4. Find "EnOcean Config UI" in the add-on list and click **Install**.
5. Start the add-on.
6. Access the UI via the add-on panel or at `http://homeassistant:8000`.

### Method 2: Manual Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/ESDN83/HA_enoceanmqtt-addon-ui.git
   ```

2. Copy the `addon/` directory to your HA add-ons folder.

3. In HA, go to **Settings** > **Add-ons** and install "EnOcean Config UI" from local add-ons.

4. Start the add-on and access the interface.

## Configuration

The add-on requires access to HA's configuration directory to read/write config files. This is configured automatically in `addon/config.yaml`:

```yaml
map:
  - config:rw
```

No additional configuration is needed. The UI will manage files in `/config/enoceanmqtt.devices` and `/config/mapping.yaml`.

## Usage

### Getting Started

1. **Access the UI**: Open the add-on panel in Home Assistant or navigate to the ingress URL.

2. **Explore EEPs**: Use the EEP Browser to find profiles matching your devices.

3. **Configure Devices**: In the Device Editor, add your EnOcean devices with their addresses and select appropriate EEPs.

4. **Create Mappings**: Use the Mapping Editor to link device data to HA entities.

5. **Validate**: Run validation checks to ensure configurations are correct.

6. **Export**: Download the generated config files and place them in your HA_enoceanmqtt addon configuration.

### Detailed Workflow

#### 1. Device Discovery
- Note your device's EnOcean address (e.g., from device manual or HA logs).
- Identify the device type and find matching EEP in the browser.

#### 2. Device Configuration
- Enter device address in hex format (e.g., 0xFFBD7480).
- Select RORG, FUNC, TYPE from dropdowns or manual entry.
- Add optional sender ID if bidirectional communication is needed.

#### 3. MQTT Mapping
- For each EEP field, specify the HA entity type (sensor, switch, etc.).
- Configure MQTT topics and payloads for discovery.
- Example mapping for a temperature sensor:
  ```yaml
  temperature:
    component: sensor
    config:
      name: "Room Temperature"
      device_class: temperature
      unit_of_measurement: "°C"
  ```

#### 4. Validation and Testing
- Use the validation tool to check YAML syntax.
- Simulate telegrams to test mappings.
- Verify MQTT topics are correctly formatted.

#### 5. Deployment
- Export configurations.
- Copy files to HA_enoceanmqtt addon config directory.
- Restart HA_enoceanmqtt addon.
- Check HA for new entities.

## API Reference

The add-on provides a REST API for programmatic access:

### GET /api/eeps
Returns all available EEPs.

**Response:**
```json
{
  "A5-02-05": {
    "rorg": "0xA5",
    "func": "0x02",
    "type": "0x05",
    "description": "Temperature Sensor",
    "fields": [...]
  }
}
```

### GET /api/devices
Returns current device configurations.

### POST /api/devices
Update device configurations.

**Body:**
```json
{
  "device_name": {
    "address": "0xFFBD7480",
    "rorg": "0xA5",
    "func": "0x02",
    "type": "0x05"
  }
}
```

### GET /api/mappings
Returns current MQTT mappings.

### POST /api/mappings
Update MQTT mappings.

### POST /api/validate
Validate a configuration file.

**Body:** Multipart form with `file` field.

### GET /api/wizards/{device_type}
Get template configuration for a device type.

### GET /api/export/{type}
Download configuration file (devices or mappings).

## Development

### Local Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/ESDN83/HA_enoceanmqtt-addon-ui.git
   cd HA_enoceanmqtt-addon-ui
   ```

2. Install dependencies:
   ```bash
   pip install -r addon/rootfs/app/requirements.txt
   ```

3. Set config directory (optional):
   ```bash
   export CONFIG_DIR=./test_config
   ```

4. Run the development server:
   ```bash
   cd addon/rootfs/app
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

5. Access at `http://localhost:8000`

### Project Structure

```
addon/
├── config.yaml          # HA addon configuration
├── Dockerfile           # Container build instructions
├── icon.png            # Addon icon
├── logo.png            # Addon logo
└── rootfs/
    └── app/
        ├── main.py         # FastAPI application
        ├── requirements.txt # Python dependencies
        └── templates/
            └── index.html  # Frontend UI
```

### Building the Addon

```bash
ha addon build --target addon/
```

## Troubleshooting

### Common Issues

**EEP Browser Not Loading**
- Check internet connection for EEP XML download.
- Verify EnOcean Alliance website is accessible.

**Configuration Not Saving**
- Ensure HA config directory is writable.
- Check addon logs for permission errors.

**Validation Errors**
- Verify hex addresses are properly formatted (0x prefix).
- Ensure RORG/FUNC/TYPE combinations are valid.

**MQTT Entities Not Appearing**
- Confirm HA_enoceanmqtt addon is running.
- Check MQTT broker configuration.
- Verify mapping.yaml syntax.

### Logs

View addon logs in Home Assistant:
- Go to **Settings** > **Add-ons** > **EnOcean Config UI** > **Log**

### Support

- Report issues on [GitHub Issues](https://github.com/ESDN83/HA_enoceanmqtt-addon-ui/issues).

## Contributing

We welcome contributions! Please:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests.
4. Commit: `git commit -m 'Add feature'`
5. Push: `git push origin feature-name`
6. Create a Pull Request.

### Development Guidelines

- Follow PEP 8 for Python code.
- Use meaningful commit messages.
- Add documentation for new features.
- Test changes locally before submitting.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Note**: This addon is not affiliated with EnOcean Alliance or Home Assistant. It is a community project to improve the EnOcean integration experience.
