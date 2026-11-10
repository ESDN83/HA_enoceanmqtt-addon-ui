# 0047. QR code pairing through Remote Commissioning

Status: proposed (v1.8.7-beta2).

## Context

Issue #67. OPUS BRiDGE actuators learn a gateway only through Remote
Commissioning, unlocked with the security code on their QR label; their
manual teach-in is for wall switches. Homegear and Mediola pair them that way.

## Decision

- Built from the public EnOcean Remote Management v2.7 (SYS_EX framing,
  UNLOCK, LOCK, PING) and Remote Commissioning v1.5 (link table metadata,
  get and set link table, apply changes, acknowledge) specifications. No other
  implementation's code is used (Homegear's license forbids derived works).
- SYS_EX telegrams are built in the app and sent as addressed radio
  telegrams, so it works with any transceiver and TCP gateway. Every one has
  the full 8-byte data field, padded with zeros (ERP1 SYS_EX is 16 bytes).
  beta2/3 sent shorter ones; a real OPUS BRiDGE answered none of them, and
  the fake transceiver now ignores them as well. Received ADT telegrams
  (RORG 0xA6) are unpacked, as addressed answers may arrive that way.
- The app's entry goes to the first index after the used ones, read first, so
  learned wall switches are never overwritten. Nothing is written when the
  sender ID is already there. The device is locked again in every case.
- The security code is used for the request only: not stored, not logged
  (TX log lines of UNLOCK and LOCK omit the data), and the UI field is a
  password field that is cleared.
- The link table entry uses the device's profile as the EEP and its channel.
  This is an assumption; the device's own expectation may differ.

## Consequences

- Experimental until confirmed on a real device.
- Only pairing; removing the entry again is not offered.
