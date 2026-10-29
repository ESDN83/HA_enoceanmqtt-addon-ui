# 0040. A light that is off keeps reporting its last level

Status: proposed (v1.8.5-beta16).

## Context

Issue #52: the light discovery uses `on_command_type: brightness`, so Home
Assistant sends a level on every turn-on. It keeps the last level only in
memory and ignores brightness 0. The app published `brightness: 0` with
every OFF, so after a Home Assistant restart a dimmer that was off had no
level, and the next plain turn-on sent 100 %. The reporter tested the fix by
hand on FUD14 channels; the devcontainer reproduces both cases (reload of
the MQTT entry, then a plain turn-on: 100 before, the last level after).

## Decision

- When a light's published state is OFF, `brightness` carries the last
  level it was on at, if one is known. SW and EDIM keep the actuator's
  real output.
- `on_command_type` stays `brightness`. The alternative (`first` / `last`
  with the app dimming to a remembered level on a bare ON) changes the
  command path of every dimmer and was not needed.

## Consequences

- Home Assistant shows no brightness for a light that is off, so nothing
  changes visibly. Anyone reading `brightness` raw from MQTT sees the last
  level while off; `state` and SW say whether it is on.
- An F6 light (on/off only) reports 100 while off, the only level it has.
