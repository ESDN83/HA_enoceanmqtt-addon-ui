# 0008. Switch state feedback: Eltako confirmation convention and commanded-state echo

Status: accepted (v1.7.0-beta8). Refines the switch status sync added in v1.7.0-beta5.

## Context

Two problems with the switch role were reported on the community forum by a
user running an Eltako FSR61 with status reporting enabled.

**1. The entity rendered as two buttons, not a toggle.** The switch discovery
config set `optimistic: true`. Home Assistant turns that into `assumed_state`,
and an assumed-state entity is drawn as a pair of on/off buttons instead of a
single toggle. `optimistic` was there because the add-on never published a
state after sending a command, so without it the entity would sit at unknown.

**2. The reported state was inverted.** An Eltako actuator confirms its state
with the opposite rocker code to the one we send as a command. It reports ON as
`0x70` (R1 = 3, BO) and OFF as `0x50` (R1 = 2, BI), while the command press for
ON is `0x50`. The beta5 status sync reused the command convention (BI = ON), so
every Eltako actuator reported inverted and users had to switch on "Invert
reported state" to compensate. Confirmed by the reporter's hardware and by
Eltako's telegram documentation.

## Decision

- The switch discovery config is **not optimistic**, so Home Assistant renders
  a real toggle.
- After sending a switch command, the add-on **echoes the commanded state** to
  the device's state topic, merged into the last known payload so the other
  fields (RSSI, Last Seen) survive. This keeps the immediate reaction that
  `optimistic` provided, including for actuators that never report their state.
  A later confirmation telegram overwrites the echo with the real value.
- Inbound status confirmation follows the **Eltako confirmation convention**:
  BO (R1 = 3) means ON, BI (R1 = 2) means OFF. The per-device "Invert reported
  state" option stays for actuators taught in the other way round.

## Consequences

- Users who enabled "Invert reported state" as a workaround in beta5 to beta7
  must turn it off after updating. Flagged prominently in the CHANGELOG, which
  is the established channel for post-update user action (ADR-0004).
- Command and confirmation now use deliberately different conventions in the
  same protocol. Both directions carry a comment saying so, because the
  mismatch is exactly what caused this bug.
- The cover role is still published as optimistic and is not covered here. It
  has the same assumed-state effect and should be revisited separately.
- Protocol assumptions keep being the weak spot in this project (ADR-0002,
  ADR-0003, and now this one). Check against real hardware or the vendor
  documentation before shipping a convention.
