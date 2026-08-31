# 0014. An Eltako shutter reports itself, and it is stopped by a tap

Status: accepted (v1.8.1-beta1). Extends ADR-0013, follows the routing rule of
ADR-0003.

## Context

Issue #39: an Eltako FJ62/12-36V DC shutter actuator could not be controlled.
The reporter had it running in openHAB, which drives it over EEP A5-3F-7F, and
supplied a debug log of both sides. Three separate defects sat behind that.

- **Stop did nothing.** The cover path sent a bare rocker release (`F6 0x00`)
  as its stop command. No real rocker ever sends a release without a press, and
  the actuator ignored it. Eltako's own documents are explicit about what a
  stop is: "Kurzes Tippen unterbricht die Bewegung sofort" (FJ62 manual) and
  "Mit eingelernten Tastern kann jederzeit unterbrochen werden!" ("Inhalte der
  Eltako-Funktelegramme"). A stop is a short tap, the same telegram pair as a
  start.
- **The actuator's own reports were dropped.** An Eltako shutter confirms with
  a rocker telegram (`0x70`/`0x50` = upper/lower end position, `0x01`/`0x02` =
  travel started up/down) and reports the time it actually ran in a 4BS
  telegram (`DB3+DB2` in 100 ms, `DB1` direction, `DB0` `0x0A`, or `0x0E` while
  blocked for pushbuttons). Both arrive from the actuator's own address under
  whatever EEP the device is configured with, so the RORG guard threw them
  away. The cover entity stayed `optimistic` with no state at all.
- **A5-3F-7F decoded to nothing useful.** The bundled EEP.xml carries the
  official "Universal" profile, four raw data bytes, because the Eltako meaning
  is manufacturer specific.

## Decision

- **Stop is a short tap of the last direction.** The command handler remembers
  the last rocker sent per cover and repeats it. The opposite direction is a
  reversal on Eltako actuators, not a stop. A stop sent while nothing is moving
  therefore starts a run, which is what the same tap on a wall switch does.
- **The shutter's own reports are read independently of the configured EEP**,
  in the same place and for the same reason as ADR-0013 does it for RPS
  switching actuators. An end position gives `open`/`closed` outright. A travel
  report is the message that the motor has stopped, so it always publishes a
  settled state, never a lingering `opening`/`closing`.
- **Position needs a per-device travel time and is measured against it.** The
  actuator reports seconds, not percent, so a percentage only exists once the
  full travel is known. `travel_time = 0` (the default) keeps open/closed and
  publishes no position. Without a previous position the travel report changes
  nothing: end positions are the synchronisation points, which is how Eltako's
  own GFVS software tracks the position.
- **A5-3F-7F ships as a bundled custom profile**, naming the Eltako fields and
  keeping the raw DB fields alongside them, so a device that uses the universal
  profile for something else still decodes.

## Consequences

- The position is read-only. Driving to a position needs the A5-3F-7F command
  path (teach-in `FF F8 0D 80` after `00 00 00 28`, travel commands carrying an
  exact runtime), which is a separate change.
- `invert` now also flips the reported direction and end positions, not only
  the commands, so a reverse-mounted shutter stays consistent in both.
- Bundling A5-3F-7F replaces the standard profile for every device using it.
  The raw DB fields are kept in the bundled profile for exactly that reason.

## Amended in 1.8.1-beta2

Field feedback on the beta from the reporter of #39 corrected two things.

- **Up is the top half of the rocker.** The cover path sent `0x50` (BI,
  bottom) for open and `0x70` (BO, top) for close, so an Eltako taught in as a
  directional pushbutton opened on close and closed on open. Eltako wires it
  the other way: "Richtungstaster oben 'Auf' und unten 'Ab'". The mapping is
  now `OPEN = 0x70`, `CLOSE = 0x50`, which also makes the commands agree with
  the confirmations this ADR reads (`0x70` = upper end position = open).
  `invert` reaches this path now as well: it was applied to D2-05 covers only,
  so ticking "Reverse direction" on an F6 cover changed nothing at all.

  **The swap does not reach existing installations.** An update that reverses
  a shutter someone has been using for months is worse than the wrong default
  it fixes, and there is no way to tell an installation that compensated for
  the old direction from one that simply lived with it. A one-time migration
  therefore ticks "Reverse direction" on every cover present at the moment of
  the update, which reproduces the old telegrams byte for byte; the flag was
  ignored on this path before, so no information is lost by overwriting it.
  Devices created afterwards get the correct direction with the box unticked.
  The migration id is recorded in `migrations.yaml` beside `devices.yaml`,
  because the keys of `devices.yaml` are device names and a marker has no
  business among them. It also makes the flag honest: whoever ends up running
  the wrong way now has one box that fixes it.
- **The UI's test buttons go through the same command path as MQTT.**
  `/api/gateway/test-actuator` carried its own copy of the rocker and dimmer
  semantics, which is why its stop button still sent a bare release after the
  MQTT path had been fixed, and why it could not know which direction to
  repeat. It now submits to the command queue like any MQTT command, so the
  routing rule of ADR-0003 and the serialised transmit path of ADR-0012 apply
  to it as well.

## Sources

- Eltako, "Inhalte der Eltako-Funktelegramme", sections *FJ62/12-36V DC,
  FJ62NP-230V* and *Bestätigungs-Telegramme bidirektionaler Aktoren*.
- Eltako, operating instructions FJ62/12-36V DC (30 200 540).
- openHAB `A5_3F_7F_EltakoFSB`, as a second implementation of the same bytes.
