# 0035. Every metering D2-01 module gets Power and Energy

Status: proposed (v1.8.5-beta11).

## Context

Issue #48: a NodOn Micro Smart Plug (D2-01-0E) reports power on its own
(CMD 7, e.g. `07 60 00 00 00 01` = 1 W), but energy only when asked; its
default reporting setting is "query only". The app created only the switch,
so neither value reached Home Assistant. ADR-0032 had solved the same for
the pilot wire module (D2-01-0C) alone.

EEP.xml gives the measurement commands (CMD 5 configure, 6 query, 7
response) to D2-01-08, 09, 0B, 0C and 0E. 0D and 12 are "no metering".

## Decision

- A D2-01 device meters when its profile has CMD 7 fields. Read from the
  profile, not a list of types, so a custom profile with measurement works
  too.
- Such a device gets *Power* (W, measurement) and *Energy* (kWh,
  total_increasing) sensors, whatever its role, without needing a sender
  ID. They are filled from CMD 7 replies and from the device's own reports.
- With a sender ID it is queried like the pilot wire module: CMD 6 for
  power and energy every five minutes, with the device's channel in the IO
  field. CMD 5 (configure automatic reporting) is still not sent; it would
  change the device's stored settings.
- Power and energy are kept in the state across telegrams, so a switch
  status does not wipe them. A measurement for another channel is ignored.
- The Pilot Wire Mode select stays specific to D2-01-0C.

## Consequences

- Existing pilot wire entities keep their unique IDs.
- A plug paired without a sender ID shows the power it reports by itself,
  but no energy until it has one.
