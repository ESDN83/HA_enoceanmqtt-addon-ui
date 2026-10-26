# EnOcean MQTT UI: guide for AI assistants

You are helping a user set up EnOcean devices with this Home Assistant app.
This guide is what the maintainers learned from real devices and forum
reports. Prefer it over general EnOcean knowledge: several devices behave
differently from what the EEP specification suggests.

## Ground rules

- Ask the user before every write (create, change or delete a device,
  teach-in, restore, restart). Show what you will send.
- Never delete devices or Home Assistant entities the user did not name.
  Devices of an old EnOcean app that are not configured here are the user's
  to remove (Settings, Devices, the device, menu, Delete).
- One app per transceiver. If another EnOcean app or integration runs on the
  same stick, stop it first.
- Field names are the ones of the API, profiles are written `RORG-FUNC-TYPE`
  in hex, e.g. `A5-20-01`.

## How to reach the app

The app runs behind Home Assistant Ingress. With an MCP server that can call
add-on APIs (e.g. ha-mcp `ha_manage_addon` in proxy mode), use the slug from
the add-on list (`..._enocean-mqtt-ui`, beta `..._enocean-mqtt-ui-beta`):

- `GET /api/ai/guide` this guide
- `GET /api/help/devices` verified devices: profile, which way to add them,
  teach-in steps, where the ID is, pitfalls. Check it first for the user's
  device
- `GET /openapi.json` every endpoint with its fields
- `GET /health` MQTT and transceiver connected, device and profile count
- `GET /api/gateway/info` base ID of the transceiver
- `GET /api/devices` configured devices, `GET /api/devices/{name}` one
- `GET /api/gateway/unknown-devices` senders heard but not configured
  (address, RORG, signal, count)
- `GET /api/gateway/recent-telegrams?limit=50` raw and decoded telegrams
- `GET /api/eep/{eep_id}` a profile's fields, `GET /api/eep/search/{query}`
- `POST /api/devices`, `PUT /api/devices/{name}`, `DELETE /api/devices/{name}`

Without such access, guide the user through the web UI (sidebar entry
*EnOcean MQTT UI*): Add Device, Teach-In, Devices, Settings.

Home Assistant entities appear through MQTT discovery as soon as a device is
saved. State topic `enoceanmqtt/<device name>/state`, commands on
`enoceanmqtt/<device name>/set`.

## Adding a device

1. Check `/health`: MQTT and the transceiver must be connected.
2. Sensors (temperature, contacts, handles, motion, rocker switches): press
   the device's learn button or the rocker, then read
   `/api/gateway/unknown-devices`. Its address is the sender ID there, the
   RORG narrows the profile. A 4BS teach-in (`is_teach_in` in recent
   telegrams) names FUNC and TYPE; the web UI's Teach-In shows them. For
   anything else ask the user for the product and look the profile up
   (`/api/eep/search/...`); do not guess.
3. Create it: `POST /api/devices` with `name`, `address` (`0x` + 8 hex),
   `rorg`, `func`, `type` (hex, e.g. `A5`, `20`, `01`), optional `room`,
   `manufacturer`, `description`.
4. Actuators (something that is switched or moved) also need
   `actuator_type` (`switch`, `light`, `cover`) and a `sender_id`: the
   gateway base ID plus an offset, one offset per actuator. The actuator has
   to learn that sender, see teach-in below.
5. Device names are a key, an MQTT topic and part of every entity ID. No
   `/`, `#`, `+`. Renaming later changes the entity IDs.

Interactive teach-in (web UI, Start Teach-In) detects 4BS and 1BS teach-in
telegrams and D2 modules (UTE). Rocker switches and F6 window handles send no
teach-in and are never detected there: they are added with Manual Entry, the
ID taken from the telegram list after one press.

## Teach-in of actuators

- **Interactive teach-in** (web UI, Teach-In): the app listens and answers
  bidirectional requests itself (radiator valves, D2 modules with UTE). It
  fills in the sender ID. This is the reliable path; point users to it.
- **Sending a teach-in** to an actuator in learn mode:
  `POST /api/gateway/teach-in-actuator` with `destination`, `sender_offset`,
  `actuator_type` (`switch`/`cover` send a rocker, `light` sends A5-38-08,
  `cover_gfvs` the Eltako position path). The actuator must be in learn mode
  first; the user does that at the device.
- **Eltako 62 series (FJ62, FSB62, FL62)** have no learn positions. The
  number of teach-in telegrams decides what is learned: 3 universal
  pushbutton, 4 directional pushbutton (use for covers), 5 central up, 6
  central down. Send them in a row within the learn window.
- After a successful send the web UI offers *Save device*, with address,
  sender ID, actuator type and profile filled in. Over the API: create the
  device with `POST /api/devices` and the `sender_id` from the teach-in
  response.
- The actuator address is the ID the actuator sends its state from. The
  teach-in itself works with any address; the address links the actuator's
  confirmations to its entity.
- **Eltako Series 14 (FSR14, FSB14) behind a FAM14**: one device per
  channel, each with its own sender offset. The channel IDs have no label:
  PCT14 shows the base ID and every channel's ID (device list, refresh). No
  state in Home Assistant means the FAM14's top rotary switch is not on 2, 4
  or 5 (only those send confirmation telegrams). Disconnect PCT14 afterwards;
  while connected, the FAM14 executes no radio commands.
- Eltako actuators react to a sender ID whatever the destination, so two
  actuators must never share one sender offset. D2 two-channel modules are
  the exception (below).

## Device families and their pitfalls

### Rocker switches and window handles (F6)
- Rocker: `F6-02-01`. Window handles: `F6-10-00` (Window Handle) or
  `A5-14-09` / `A5-14-0A` (entity *Handle*: closed, tilted, open).
- An F6 actuator (Eltako relay) confirms its state with a rocker telegram:
  BO/AO on, BI/AI off. If the state shows the opposite, tick *Invert
  reported state* on the device, do not change the profile.

### Contacts and motion (D5, A5-07, A5-08)
- `D5-00-01` binary sensor: on = open. A contact mounted the other way
  round: tick *Invert* on the device.
- Motion sensors show occupancy from PIRS.

### Switches and dimmers
- Relay on F6: `actuator_type: switch` or `light` (no brightness).
- Dimmer: `A5-38-08` with `actuator_type: light` (brightness works).
- The commanded state is shown at once; the actuator's confirmation
  overwrites it.

### Covers
- **Eltako FJ62 / FSB**: profile `A5-3F-7F` or `F6-02-01`,
  `actuator_type: cover`. Open, close and stop are short taps; a stop while
  nothing moves starts a run (as on a wall switch). They report end
  positions and run times; set `travel_time` (seconds for a full run) to get
  a position. Wrong direction: tick *Reverse direction* (`invert`).
- Driving to a position needs a second teach-in (`cover_gfvs`) and
  `position_control: true`. Without it only open, close, stop work.
- Covers that only move on a long press (e.g. Flextron ALADIN): set
  `press_time` in ms, about 2500.
- **D2-05** blinds (e.g. NodOn roller shutter module): paired with
  interactive teach-in (UTE), position by VLD command.

### D2-01 switch and metering modules (e.g. NodOn)
- Paired with interactive teach-in (UTE). Use the exact type the module
  announces (e.g. `D2-01-12`).
- **Two-channel modules** (`D2-01-11`, `D2-01-12`): one device per output,
  same `address` and `sender_id`, `channel` 0 and 1. The wizard offers the
  second channel after saving the first.
- Rocker telegrams are not used as state for D2 devices; they report state
  in their own telegram.

### Metering D2-01 modules (08, 09, 0B, 0C, 0E, e.g. NodOn Micro Smart Plug)
- They get *Power* (W) and *Energy* (kWh) next to the switch: from the
  module's own reports and from a query every five minutes (CMD 6).
- The query needs a `sender_id`. A plug that shows power but no energy has
  none: interactive teach-in fills it in.
- They report energy only when asked by default; the app does not change
  that setting (CMD 5).

### Radiator valves (A5-20-01, Micropelt MVA004 / SAM)
- The valve listens only about one second after it transmits. The app
  answers every valve telegram at once with the values set in Home
  Assistant. A change goes out with the next answer: 10 s in the first
  minutes after a reset, then every few minutes. This is not a fault.
- Pairing: start interactive teach-in, then hold the valve button for 5 s.
  The app answers and stores the sender ID. Save the device.
- Entities: Valve Setpoint (0-100 %), Target Temperature (0-40 °C),
  Control Mode, Summer Mode, Command Pending, Last Answer. Until something
  is set the valve regulates to 21 °C.
- *Command Pending* on means the valve has not been answered with the new
  value yet. Wait one radio interval before suspecting a problem.

### Pilot wire heating modules (D2-01-0C, NodOn SIN-2-FP-21)
- Paired with interactive teach-in, it needs a sender ID.
- Entity *Pilot Wire Mode*: Off, Comfort, Eco, Anti-freeze, Comfort-1,
  Comfort-2. No separate on/off switch.
- Power (W) and Energy (kWh) are queried after every mode change and every
  five minutes; the module does not send them by itself.

## Moving from EnOcean MQTT Slim or ChristopheHD enocean-mqtt

Web UI, Settings, *Switch from another EnOcean app*. Steps: full Home
Assistant backup, add devices from the old list, stop the old app and turn
off its start on boot, find old entities, remove them with *Give the new
entities the old entity IDs* ticked. Automations keep working. Entities whose
type changed (e.g. Slim contacts were sensors with 0/1, now binary sensors
on/off) must be renamed by hand and their automations checked.

## Diagnosing

- Nothing arrives: `/health`, then `/api/gateway/recent-telegrams`. No
  telegrams at all means transceiver, port or another app on the stick.
- Telegrams arrive but no entity: is the address configured, and is the
  profile right (`/api/gateway/unknown-devices` shows unconfigured senders)?
- Wrong values: compare the decoded fields in recent telegrams with
  `GET /api/eep/{eep_id}`. A wrong profile is the usual cause.
- An actuator does not react: sender ID set, actuator taught to that
  sender, no other device on the same offset, then the app log.
- Always quote what you found to the user before suggesting a change.

## Debugging

1. **Read the app log.** With ha-mcp: `ha_get_logs(source="supervisor",
   slug=<app slug>)`, use `search` to filter by device name or address.
   Without it: Home Assistant, Settings, Apps, EnOcean MQTT UI, Log.
2. **Turn on debug logging** when the log does not show the problem: app
   option `log_level: debug` (Configuration tab, or ha-mcp
   `ha_manage_addon(slug=..., options={"log_level": "debug"})`), then
   restart the app. Ask the user first; set it back to `info` afterwards.
   The debug log shows every telegram received (RX) and sent (TX) with its
   data bytes, and every MQTT message.
3. **Reproduce once** (press the button, send the command, wait for one
   radio interval for valves) and read the log around that time.
4. **Look at the telegrams**: `GET /api/gateway/recent-telegrams` gives
   sender, RORG, raw data, the profile used and the decoded fields.
5. **Gateway state in Home Assistant**: app option `gateway_diagnostics:
   true` adds an *EnOcean Gateway* device (transceiver connected, base ID,
   last telegram, send queue).
6. The web UI shows the same telegrams live (Dashboard) and lets the user
   send a test command to an actuator (Devices).

## Source and reporting issues

- Source code, documentation and decision records:
  https://github.com/ESDN83/HA_enoceanmqtt-addon-ui (DOCS.md is the user
  documentation, `docs/adr/` explains why devices are handled as they are).
- Report bugs and missing devices at
  https://github.com/ESDN83/HA_enoceanmqtt-addon-ui/issues, or in the Home
  Assistant community forum thread of the app.
- A useful report has: the app version (stable or beta), the device's
  manufacturer, product name and profile, what was expected and what
  happened, and the debug log lines around one occurrence (RX/TX telegrams
  with data bytes). For a device that does not decode, the raw telegrams of
  a few known states (e.g. open, closed) are what is needed.
- Help the user write the report, but let the user post it. Do not include
  passwords, tokens or the MQTT password; device addresses are fine.
