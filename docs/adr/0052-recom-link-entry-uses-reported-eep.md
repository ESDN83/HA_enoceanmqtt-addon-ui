# 0052. The link table entry uses the EEP the device reports

Status: proposed (beta).

## Context

First test of 1.8.7-beta8 on a real OPUS 563.010 (USB310, forum 1026367,
2026-11-13). Ping, link table metadata and reading the table worked. Then:

- SET LINK TABLE with EEP D2-01-00 (the profile configured, and listed in
  our catalog) got no answer three times; the same entry with D2-01-01 was
  acknowledged. The ping answer `d2 04 08 37` decodes to D2-01-01 (RORG 8,
  FUNC 6, TYPE 7 bits, as FHEM reads it).
- APPLY CHANGES (0x226, 0x80) was never acknowledged, yet the actuator
  switched from the Base ID right after the entry was written. FHEM does not
  wait for an answer to it either.

## Decision

- Decode the device's EEP from its ping answer and use it for the link table
  entry. A different configured profile is logged as a warning and returned
  as `device_eep`; the device configuration is not changed by the app.
- APPLY CHANGES is sent once and waited for two seconds; without an answer
  the pairing still succeeds, with a step saying so.
- A SET LINK TABLE without answer fails with a message naming sender and EEP.
- Catalog: 563.010 is D2-01-01, QR pairing with the Base ID as sender.

## Consequences

- Devices whose ping answer carries no EEP keep using the configured profile.
