# EnOcean MQTT UI

![EnOcean MQTT Dashboard](https://github.com/user-attachments/assets/6cc73258-3848-4ee0-9aef-250efa3b9080)

## About

All-in-One EnOcean to MQTT bridge with a modern web UI for Home Assistant.
This app replaces the need for separate EnOcean bridges and YAML configuration.
Add your EnOcean devices visually, browse EEP profiles, and manage MQTT mappings,
all from within Home Assistant.

### Key Features

- **Visual Device Wizard**: Add, edit and remove EnOcean devices through a web UI
- **Teach-In Mode**: Automatic device detection when pressing the learn button
- **96+ EEP Profiles**: Built-in EnOcean Equipment Profile browser
- **Custom Profiles**: Create profiles for non-standard devices (e.g., Kessel Staufix)
- **EEP.xml Upload**: Upload your own EEP.xml profile database or use the bundled one
- **MQTT Discovery**: Devices appear automatically in Home Assistant
- **Live Telegram Monitor**: Debug incoming EnOcean telegrams in real-time
- **Unknown Device Detection**: Detect and quick-add unconfigured devices
- **State Persistence**: Restore device states after restart
- **Actuator Control**: Control Eltako dimmers, switches, and blinds with teach-in support
- **HA Entity Mapping Overrides**: Customize HA mappings per EEP profile with inline editor and auto-fill
- **Advanced Mapping Fields**: state_class, entity_category, expire_after, force_update, display precision, value_template
- **Visual & Text Mode Editor**: Toggle between visual form and YAML text editor for mapping overrides
- **Fork Standard Profiles**: Create custom copies of standard EEP profiles to edit fields and mappings
- **YAML-Based Config**: All configuration files (devices, mappings, overrides) stored as YAML
- **Export/Import YAML**: Full configuration export/import as YAML files
- **Local Backups**: Create, list, restore, and delete local backups (devices, mappings, custom profiles, overrides)
- **Dark Mode**: Automatic light/dark theme based on your Home Assistant settings
- **Multi-Language UI**: Auto-detects browser language (11 languages supported)
- **Mobile Friendly**: Responsive UI with sidebar navigation

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
| **MSC (D1)** | Manufacturer-specific | Custom devices |

## Quick Start

1. **Configure** your EnOcean USB serial port in the app settings
2. **Start** the app and open the Web UI via the sidebar
3. **Add a device**: Click "Add Device", choose Teach-In, and press the learn button on your EnOcean device
4. **Done**: The device appears automatically in Home Assistant via MQTT Discovery

> **MQTT:** The app automatically connects to Home Assistant's MQTT broker, so make sure a broker (e.g. the Mosquitto app) and the MQTT integration are set up. An external broker can be configured in the Web UI under Settings.

## Web UI

![Devices](https://github.com/user-attachments/assets/0e7981a0-9db0-4e63-9bd1-2bd4d20c5c85)

### Dashboard
Overview with connection status, device counts, recent telegrams and unknown device detection.

### Devices
List and manage all configured EnOcean devices. Add, edit, or remove devices.

### EEP Profiles
Browse the complete EnOcean Equipment Profile tree with dedicated sections for
Custom Profiles, Customized Mappings, and the standard EEP tree. Search across
all profiles and view field definitions.

![EEP Profiles](https://github.com/user-attachments/assets/fa4d4142-b873-4862-823e-815bec9fc7ac)

### Entity Mappings
Define how EEP profile fields map to Home Assistant entities (sensor, binary_sensor,
switch, light, cover, etc.). Each EEP profile detail view includes a "Customize" button
to override the default mapping, with auto-fill from EEP.xml field definitions and
per-profile save/reset. Advanced fields like `state_class`, `entity_category`,
`expire_after`, `force_update`, and `value_template` are supported.

Toggle between Visual and Text (YAML) editing modes for full control:

![Text Mode](https://github.com/user-attachments/assets/d6b188da-a61e-4ec1-aae3-c01bb805b45e)

### Custom & Forked Profiles
Create fully custom EEP profiles for non-standard devices, or "fork" a standard
profile to customize its Telegram Fields and HA mappings together.

Some profiles ship with the app (marked *bundled*, e.g. A5-3F-7F for Eltako
shutters). Editing one keeps your version across updates; *Reset to bundled
version* brings the shipped one back (your edit is kept as a `.bak` file).
*Remove* hides a bundled profile for good; it is listed under *Removed bundled
profiles* with a *Restore* button.

When a mapping field is removed or changed, its old entity is removed from
Home Assistant at the next start of the app.

![Custom Profile](https://github.com/user-attachments/assets/8da98b5c-14cf-4e4e-a26a-cc31aac98e67)

### Add Device
Wizard for adding new devices: Teach-In (the device announces itself),
Actuator Teach-In (the app teaches an Eltako actuator) or Manual Entry. The
page starts with a short guide: which way fits your device, where the ID is,
what the profile is, and a searchable list of verified devices with their
steps. Rocker switches send no teach-in: press one, take its ID from the
Dashboard and use Manual Entry.

### Settings
Export/import full configuration as YAML, upload custom EEP.xml, local backups
(create/list/restore/delete, includes devices, mappings, custom profiles, and overrides),
view system information, restart services.

![Settings](https://github.com/user-attachments/assets/370072b1-7219-4566-a733-2c9e58b018fa)

## Configuration

### Serial Port

Select your EnOcean USB transceiver from the list of detected serial devices
(e.g. `/dev/ttyUSB0` for a USB300, `/dev/ttyAMA0` for a Raspberry Pi GPIO). A
device must be selected here, Home Assistant can't save this field empty. A
plugged-in USB gateway usually appears with a recognizable name (e.g. something
containing "USB 300").

**Using TCP instead?** A TCP connection takes priority over the serial port, so
just pick any device from the list; it will be ignored while a TCP port is set.

### TCP Port (Remote Connection)

Connect to a remote EnOcean transceiver over the network. Use this when your
EnOcean USB stick is connected to a USB-over-IP device (e.g., SMLIGHT SLZB-MR5U
USB-Passthrough, Silex DS-700, or any ser2net-based setup).

Format: `tcp:HOST:PORT` (e.g., `tcp:192.168.1.118:8638`)

When both serial and TCP are configured, **TCP takes priority**.

### MQTT Settings

By default the app automatically connects to the MQTT broker provided by
Home Assistant (the Mosquitto broker app): leave **Host** empty for this.

To use an **external MQTT broker** (e.g. a standalone Mosquitto container on
UNRAID, Synology, or another server), fill in the **Host** field. When a host is
set, the app connects there directly instead of using the HA broker, and the
Port/Username/Password below apply. This also works when you have no MQTT broker
app installed in Home Assistant at all.

| Option | Default | Description |
|--------|---------|-------------|
| **Host** | *(empty)* | External broker hostname/IP. Leave empty to use Home Assistant's MQTT broker |
| **Port** | `1883` | Broker port (used only when Host is set) |
| **Username** | *(empty)* | Broker username (used only when Host is set; leave empty for anonymous) |
| **Password** | *(empty)* | Broker password (used only when Host is set) |
| **Discovery Prefix** | `homeassistant` | MQTT discovery prefix for HA auto-detection |
| **Topic Prefix** | `enoceanmqtt` | Topics are created as `enoceanmqtt/{device}/state` |
| **Client ID** | `enocean_gateway` | Unique MQTT client identifier |

> **Note:** When using an external broker, make sure Home Assistant's own MQTT
> integration points at the **same** broker, otherwise HA won't see the
> discovery messages and no entities will appear.

### Cache Device States

When enabled (default), the app persists the last known state of all devices.
After a restart, these states are republished so that infrequent sensors (like a
Kessel Staufix that only reports every 8-10 hours) don't show as "unavailable".

## Switching from EnOcean MQTT Slim or ChristopheHD enocean-mqtt

Settings → *Switch from another EnOcean app*. The **How it works** button there
shows the same steps. No warranty: make a full Home Assistant backup first.

### Steps

1. Leave the old app running for now.
2. **Add devices.** ChristopheHD is read from `/config/enoceanmqtt.devices`,
   Slim from the running Slim app; either can also be uploaded as a file.
   Check the names and add the ticked devices. Sections marked `ignore` or
   defined only by `model =` are listed as skipped; add those by hand.
3. Stop the old app and turn off *Start on boot*. Only one app can use the
   transceiver.
4. **Find old entities.** The table lists the old app's entities, but only
   for devices that now exist in this app, each with the new entity that
   takes over its entity ID (same device, same value, same type). While Slim
   is still running this step is refused, since Slim would publish them
   again.
5. **Remove.** This clears the old entities' MQTT discovery messages, so Home
   Assistant drops exactly those entities; the Home Assistant device and the
   new entities stay. With *Give the new entities the old entity IDs* ticked
   (the default), the new entities are renamed right after, so automations,
   dashboards and the history carry on.
6. Check actuators (light, switch, cover): type and sender ID may need
   setting.

### Notes in the table

| Note | Meaning | What to do |
|---|---|---|
| *(new entity shown)* | Paired, gets the old ID. | Nothing. |
| no matching new entity | This app has no entity for that value. | Remove it, or keep it if you still need it. |
| new entity has another type, rename by hand | Same value, different type, e.g. a sensor became a binary sensor. Home Assistant cannot rename across types. | Rename by hand (below), then check automations. |
| several candidates, rename by hand | More than one old entity fits. | Rename by hand. |
| the new entity already has this ID | Done in an earlier run. | Remove the old one. |

### Renaming by hand

1. Remove the old entity first, so its ID is free.
2. Settings → Entities, open the new entity, gear icon, *Entity ID*, enter
   the old ID, save.

### Type changes to check

- **Slim door/window contacts (D5-00-01)** were sensors with `0`/`1`. Here
  they are binary sensors with `on` (open) / `off` (closed). Automations that
  compare with `0` or `1` need updating.
- **Contacts and motion sensors** can be flipped per device: open the device,
  tick *Invert binary sensors*. Use it for a contact mounted the other way
  round.

## Troubleshooting

### EnOcean Gateway Not Connecting
- Verify the correct serial port is selected in the app settings
- Check that no other app is using the same serial port
- Try unplugging and reconnecting the USB transceiver

### Devices Not Appearing in Home Assistant
- Check that MQTT is connected (green badge in the Web UI)
- Verify the MQTT discovery prefix matches your HA config (default: `homeassistant`)
- Check the app log for errors

### Teach-In Not Working
- Make sure the EnOcean gateway shows "connected" (green status)
- Press the teach-in button firmly on your device
- Some devices require multiple presses or holding the button

### Eltako 61 Series (FSR61, FUD61, FSB61, OPUS 561.164)
- Teach-in: upper rotary switch to **LRN**, not CLR. On CLR the actuator
  deletes every sensor it hears.
- In LRN it learns the next telegram it hears, from any sender. Pause
  automations that switch other Eltako devices while teaching in.
- No state in Home Assistant: the confirmation telegrams are off from the
  factory. Upper switch to CLR, then within 10 s the lower switch 3 times to
  the **left** stop and back; this toggles them. 3 times to the right
  deletes every learned sensor.
- FSB61: use GS2 or GS3 on the lower switch. GS4 and GR are static (the
  motor runs only while the button is held), so a tap from the app moves the
  shutter only briefly. The OPUS 561.164 is a rebranded FSB61NP.

### Eltako 62 Series (FJ62, FSB62, FL62)
These actuators have no learn positions, only learn mode on and off. The number
of telegrams they receive decides which kind of sender is learned, so "Send
Teach-In" has to be clicked several times in a row:

| Sender type | Clicks |
|---|---|
| Universal pushbutton | 3 |
| Directional pushbutton (use this for a cover) | 4 |
| Central control up | 5 |
| Central control down | 6 |

### Eltako Series 14 (FSR14, FSB14 on a FAM14)
- One device in this app per channel, each with its own sender offset: an
  FSR14-4x is four devices.
- The channels have no printed radio ID. Connect PCT14 to the FAM14,
  refresh the device list: it shows each channel's ID. Use it as *Actuator
  Address*. Disconnect PCT14 afterwards.
- No state in Home Assistant: the FAM14 sends confirmation telegrams only
  with its top rotary switch on 2, 4 or 5.

### Eltako Shutter Actuators (FJ62, FSB)
- Open and close are short rocker taps, and so is stop: a tap while the shutter
  runs interrupts it. A stop sent while nothing is moving starts a run instead,
  exactly as it would on a wall switch.
- Up is the top half of the rocker, down the bottom one, the way Eltako wires a
  directional pushbutton. If your shutter runs the wrong way, tick **Reverse
  direction** on the device. Covers that existed before 1.8.1 have that box
  ticked automatically, so the update leaves them running exactly as they were;
  untick it if the shutter has been running the wrong way round.
- These actuators report themselves: an end position, the start of a run, and
  the time they actually ran. The add-on turns that into open/closed without
  any further configuration.
- Set **Travel time (s)** on the device to get a position as well. It is the
  number of seconds for a full run, and the position is synchronised whenever
  the shutter reaches an end position. The position is read-only for now.


### Radiator Valves (A5-20-01, e.g. Micropelt MVA004 / SAM)
- The valve only listens for about a second after it transmits, so the app
  answers every telegram from it at once. A value you set in Home Assistant is
  stored and goes out with the next answer, after at most one radio interval
  (10 s in the first minutes after a reset, then every few minutes).
- Pairing: start **Teach-In** in the app, then press the valve's button for
  5 s. The app answers the valve's request (green flash) and fills in the
  Sender ID; save the device with it. A valve that is already set up is
  answered too, with the Sender ID it has.
- Entities: **Valve Setpoint** (0-100 %), **Target Temperature** (0-40 °C),
  **Control Mode** (valve / temperature) and **Summer Mode**. Setting the
  setpoint or the temperature switches the mode to match. Until you set
  anything the valve regulates itself to 21 °C.
- **Command Pending** is on while a value you set waits for the valve's next
  telegram, and goes off once the valve has been answered with it. **Last
  Answer** shows when the valve was last answered.
- The valve uses its own temperature sensor. Summer mode makes it report only
  every few hours.


### Pilot Wire Heating Modules (D2-01-0C, e.g. NodOn SIN-2-FP-21)
- Pair the module with **Teach-In**; it needs a Sender ID, which the teach-in
  fills in.
- **Pilot Wire Mode** sets Off, Comfort, Eco, Anti-freeze, Comfort-1 or
  Comfort-2. A mode chosen at the module's own button is shown as well.
- **Power** (W) and **Energy** (kWh) are read from the module after every
  mode change and every five minutes; the module does not send them by
  itself. Energy works with the Home Assistant energy dashboard.

### Metering Modules (D2-01-08, 09, 0B, 0C, 0E, e.g. NodOn Micro Smart Plug)
- **Power** (W) and **Energy** (kWh) appear next to the switch.
- Power arrives whenever the module reports it. Energy is asked for every
  five minutes, which needs the device's Sender ID (filled in by the
  teach-in).

## AI Assistants

An AI assistant connected to Home Assistant through an MCP server that can
call app APIs (e.g. ha-mcp) can read a setup guide from the running app at
`/api/ai/guide`: the steps to add and teach in devices and the pitfalls of
specific devices. It is told to ask you before changing anything.

## Support

- Report issues on [GitHub](https://github.com/ESDN83/HA_enoceanmqtt-addon-ui/issues)
- Check logs in Home Assistant: Settings > Apps > EnOcean MQTT UI > Log
