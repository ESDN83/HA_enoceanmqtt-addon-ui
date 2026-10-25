# 0032. VLD telegrams decode by command; pilot wire modules are queried

Status: proposed (v1.8.5-beta7, amended in v1.8.5-beta8).

## Context

A NodOn SIN-2-FP-21 pilot wire module (D2-01-0C) paired fine but could not
be controlled, and showed no power or energy (forum post 78, debug log of a
real module cycling through its modes: `0A 02`, `0A 03`, `0A 00`, `0A 01`).

- EEP.xml already describes D2-01-0C with every command: CMD 4 status, CMD 7
  measurement, CMD 8/9/10 pilot wire mode, each field tagged with its command.
  The decoder ignored the tags and applied all layouts to every telegram, so
  `0A 02` (Eco) came out as DV, IO, OC, EL, UN and PM together.
- No entity or command existed for the mode or the measurements.
- In four minutes of log the module sent no measurement on its own.

Formats checked against two implementations: Jeedom's D2-01-0C profile (EEP
2.6.4) and FHEM `10_EnOcean.pm` (set `08 0M`, get mode `09`, get measurement
`06 <query << 5 | channel>`, reply CMD 7 with unit 0 Ws, 1 Wh, 2 kWh, 3 W,
4 kW and a 32-bit value, CMD 10 mode in the low three bits).

## Decision

- `_fields_for_command`: a field group tagged with a command applies only if
  that group's own CMD field, read where the group's layout puts it, holds
  its ID. Untagged fields always apply; if no group matches, everything is
  decoded as before. Generic for D2-01 and D2-05.
- `core/pilot_wire.py`: a *Pilot Wire Mode* select sends CMD 8 and reads the
  result back with CMD 9; *Power* (W) and *Energy* (kWh, total_increasing)
  come from CMD 6 queries after a mode change and every 5 minutes. The
  module's own reporting (CMD 5) is not configured: that would change its
  stored settings, and the queries work without it.
- A reply carries the mode or one measurement, and every published state
  replaces the retained one, so a D2-01-0C state is merged with the last
  mode, power and energy.
- The mode is handled whatever role the device has for its output (teach-in
  makes a D2-01 a switch).

## Consequences

- Decoded D2 states lose fields of other commands (DV, REPO, RM, ...). No
  mapping read them; D2-01-12, D2-05-00/02, D2-01-03 states are unchanged,
  and the same 21 actuator commands produce byte-identical telegrams and
  confirmations on 1.8.4 and this build.
- One query cycle is three telegrams per module every five minutes.
- The fake TCM plays a pilot wire module (mode set/query, power/energy).

## Amendment (v1.8.5-beta8): no output switch for a pilot wire module

Teach-in gives every D2-01 the switch role, so a pilot wire module also got
the generic output switch (CMD 1: 0 % Off, 100 % Comfort) next to the mode
select, which a tester took for a leftover (forum post 80). For D2-01-0C the
actuator entity is no longer published; the startup cleanup (ADR-0026)
removes the existing one. Other D2-01 switches are unchanged.
