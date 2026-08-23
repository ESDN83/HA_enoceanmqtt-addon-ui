# 0013. RPS actuator status is read independently of the configured EEP and role

Status: accepted (v1.8.0-beta14). Extends ADR-0008, follows the routing rule of ADR-0003.

## Context

A community forum user reported an Eltako FL62NP light actuator: teach-in
worked, switching over F6-02-01 worked, the switching status was visible under
the device in the add-on, and the Home Assistant entity still read `unknown`.

ADR-0008 added status feedback for RPS actuators, but it was reachable only
through one narrow path in `_process_telegram`: role `switch`, RORG `F6`, and a
device whose configured EEP profile also carries RORG `F6`. Three ordinary
configurations fell outside it.

- **Role `light` on a switching actuator.** The role list offers "Actuator:
  Light / Dimmer", which is what a user picks for a light actuator. The light
  branch only ever looked at A5-38-08 dimmer frames, so an RPS confirmation
  produced no state at all. The same role also sent A5-38-08 dimmer commands to
  a module that only understands rocker presses, so the entity could not
  control the lamp either.
- **A non-F6 EEP on an RPS actuator.** Eltako's own teach-in tables point at
  A5-38-08 for several actuators, and the RORG guard (added so an FD62NPN's F6
  and D1 chatter is not decoded with an A5 profile) dropped the confirmation
  before any state could be derived.
- **Rocker A confirmations.** Only BO/BI (`0x70`/`0x50`) were recognised. A
  module taught in on the A channel confirms with `0x30`/`0x10`.

In all three cases the telegram still appeared in the device's telegram list,
because the buffer is filled from the raw telegram, which is why the add-on
looked like it knew the state while MQTT did not.

A fourth defect sat behind them: a rocker release (`0x00`) carries no state,
and publishing it as it is removed `state` from the retained state topic. The
entity survived that at runtime, because Home Assistant ignores a value
template that renders empty, but it came back as `unknown` after every restart.

## Decision

- The RPS actuator status is derived in one place, `_rps_actuator_state`, from
  the telegram and the device alone: RORG `F6`, energy bow pressed, any of the
  four rocker codes, role `light` or `switch`. It runs **before** the RORG
  guard, so it also works for an actuator taught in under a non-F6 EEP, where
  the telegram is published with the state and the metadata but without decoded
  fields.
- AO and BO mean ON, AI and BI mean OFF, keeping the Eltako confirmation
  convention of ADR-0008 for both rockers. "Invert reported state" still covers
  actuators taught in the other way round.
- A light on an F6 EEP is switched with a rocker press+release, not with
  A5-38-08, in the MQTT command route and in the add-on's own test buttons.
  This is the EEP-first rule of ADR-0003 applied to the light role.
- Its discovery config drops the brightness topics, because a relay cannot dim
  and a slider that does nothing is worse than no slider.
- A telegram that carries no state for an actuator repeats the last known
  state instead of publishing a payload without it.

## Consequences

- An RPS light actuator now works in either role. "Actuator: Switch" gives a
  switch entity, "Actuator: Light / Dimmer" gives a light entity, both with
  status feedback.
- Existing light entities on an F6 EEP lose their brightness slider on the next
  discovery publish. They never controlled anything.
- Rocker A confirmations are newly recognised. An actuator that was reporting
  nothing may now report, and if it was taught in the other way round the
  "Invert reported state" option is the fix, as before.
- The retained state topic of an actuator always carries `state` once a state
  is known, so the entity restores after a Home Assistant restart.
- Verified on the devcontainer Home Assistant with the fake transceiver playing
  the actuator: a light role on F6 now sends a rocker press and follows the
  confirmation, an unsolicited status telegram moves the entity with no command
  involved, rocker A reports, an actuator on an A5-38-08 profile reports, and
  after a release the entity restores from the retained topic across an MQTT
  config entry reload instead of going Unknown. The A5-38-08 dimmer path, the
  switch role, the invert option and the F6 sensor role were re-checked
  unchanged. Not tested on an FL62NP; field confirmation by the reporter is
  still open.
