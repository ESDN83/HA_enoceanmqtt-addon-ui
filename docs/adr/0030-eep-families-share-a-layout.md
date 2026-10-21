# 0030. Missing D2-01 / D2-05 types use their family's layout; D2 actuators ignore rocker telegrams

Status: proposed (v1.8.5-beta5).

## Context

A forum user's OPUS installation (thread 1026367: 563.031 blind D2-05-02,
563.076 dimmer D2-01-03, 563.010 switch) was tested in the devcontainer with
the telegrams from his log:

- EEP.xml (from upstream ChristopheHD) lists D2-01-01, -08..-0F and -12, and
  D2-05-00 and -02. A device of another type had no profile, so
  `_process_telegram` dropped every telegram with "Unknown EEP profile".
  Commands go by family (D2-01, D2-05) and worked; the state never came back.
- The OPUS blind sends a rocker telegram (`F6 70`) from its own address when
  its button is pressed, followed by its D2 status. The Eltako rule that
  reads a rocker telegram from an actuator as its confirmation (ADR-0013,
  ADR-0014) set the blind open until the status corrected it, and `F6 50`
  would have set it closed.

## Decision

- After EEP.xml is loaded, every missing type of D2-01 (0x00-0x12) and D2-05
  (0x00-0x05) gets the fields of D2-01-01 / D2-05-00. The EEP specification
  defines one set of commands per family; the types only differ in what a
  device supports. D2-01-01 is the template rather than a metering type:
  the decoder does not filter fields by command, and the metering fields
  would add meaningless values to every status. They count as base profiles,
  so a custom profile still overrides them.
- For a device whose EEP is D2 the rocker-as-confirmation rules (switch,
  light, Eltako cover state and travel) do not run. A VLD actuator reports
  its state in its own D2 telegram.

## Consequences

- The profile list grows from 97 to 110 entries.
- Metering D2-01 types (e.g. -02, -04, -05) decode status but not
  measurements.
- Verified in the devcontainer: dimmer status 25 % shows brightness 64/255,
  off at the wall shows off, the blind's button no longer moves its state,
  Eltako FL62 confirmations, NodOn D2-05-00 and D2-01-12 unchanged.
