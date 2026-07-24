# 0003. Outbound command routing is EEP-first

Status: accepted (v1.7.0-beta1).

## Context

Different EnOcean actuators need different outbound telegrams:
- Eltako dimmers use A5-38-08 central command dimming.
- Eltako switches and covers are driven by simulated F6 rocker presses (broadcast).
- D2-01 electronic switches and D2-05 blinds are VLD (RORG D2) devices that only react to addressed telegrams, not F6.

`_handle_device_command` originally branched on the device role (light, switch, cover) first, and the D2-01 handling sat inside the `switch` branch only. A D2-01 module registered as a "light" therefore received A5-38-08 telegrams and never reacted (issue #23). An F6 broadcast also leaks: it can move other broadcast-listening actuators.

The command format was verified against the official HA `enocean` integration and the bundled EEP.xml: D2-01 uses CMD 1 with three bytes (`CMD`, `DV|IO`, `OV`). The "CMD 4" in the original report was a mislabel.

## Decision

Route **by EEP first**: `D2-01-xx` and `D2-05-xx` devices get their proper addressed VLD telegram regardless of the chosen role. Only non-D2 devices fall through to the role-based path (A5-38-08 for light, F6 rocker simulation for switch and cover). A "light" role on a D2-01 sends its brightness as the output value.

## Consequences

- D2 actuators work regardless of the role label.
- F6 remains broadcast (each Eltako actuator needs its own sender offset); D2 is addressed (one sender can drive many, and the channel selects the output). See ADR-0005.
- Protocol assumptions must be checked against the spec and a second implementation before shipping. This ADR and ADR-0002 both came from wrong assumptions.
