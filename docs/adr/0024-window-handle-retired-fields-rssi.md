# 0024. Window handles read CT, retired fields are cleared, RSSI from byte 5

Status: proposed (v1.8.4-beta9).

## Context

sp00ky (forum post 53) reported two things for an Eltako FFG7B window handle
(A5-14-09): the contact stayed unknown, and RSSI was missing. The owner's own
installation showed no RSSI either.

- The A5-14-09 and A5-14-0A mappings read `OC` and `ILL`. EEP.xml has `CT`
  (0 closed, 1 tilt, 3 open), `SVC` and, for 0A, `VIB`. An automated check of
  all 71 default mappings against EEP.xml found more profiles with the same
  kind of mismatch; those are left for a separate audit.
- RSSI was read from optional byte 4. ESP3 puts dBm at byte 5, after
  SubTelNum (1) and the destination ID (4); byte 4 is the last byte of the
  destination, 0xFF for every broadcast, which the range check rejected. The
  kipe enocean library reads `optional[5]`, and the devcontainer's fake
  transceiver sends it there too. RSSI was 0 for everyone.

## Decision

- A5-14-09/0A: the `OC` key stays (unique_id) as the window binary_sensor,
  open when CT is tilt or open. A new `CT` sensor shows closed, tilted or
  open.
- `ILL` is retired. A retained discovery config outlives the mapping that
  made it, so `RETIRED_FIELDS` lists such fields per EEP and both publish
  paths clear their configs. Without that, the entity would stay unknown.
- dBm is read from optional byte 5. A missing level publishes RSSI as
  unknown in HA, not 0 dBm.

## Consequences

- Window handles work and RSSI appears without user action.
- The Illuminance entity of these devices disappears.
- Automations on the handle's window entity now see tilted as open.
