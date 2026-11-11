# 0049. Radio repeater over Remote Commissioning

Status: proposed (beta, experimental).

## Context

A device the gateway barely reaches (RSSI about -80 dBm or worse) misses
commands: a NodOn SIN-2-2-01 at -83 dBm, dipping to -95, needed two to five
presses. Mains-powered modules such as the NodOn in-wall range can repeat
telegrams, but the repeater is off by default and NodOn offers no button for
it: their guide says to set it "on your gateway". That setting is part of
Remote Commissioning, which the app already speaks for QR pairing
(ADR-0047).

## Decision

- `Recom.repeater()` sends PING, GET REPEATER FUNCTIONS (0x250, answer
  0x850), and for a change SET REPEATER FUNCTIONS (0x251, no answer)
  followed by 0x250 again (Remote Commissioning v1.3, A 1.1 and A 1.2).
  The result carries the value before, the value read back and whether it
  equals the one written.
- The data byte is filled from the most significant bit in the order the
  spec lists the fields: repeater function (2 bits), level (2 bits), filter
  structure (1 bit). Level 1 is 0x50, level 2 0x60, off 0x00. The spec gives
  no bit offsets, which is why the value is read back and the raw byte shown.
- Unlock: with a security code (8 hex digits or the QR label) it is UNLOCK
  twice before and LOCK after, the code used for that call only, never
  stored or logged. Without one the device has to be in its unlock period
  after power-up (5 minutes, Remote Management 2.91); a missing answer says
  so. NodOn in-wall modules have no QR label, so this is their route.
- Sender: the device's sender ID, else base ID + 1.
- UI: a *Radio repeater* card on the page of every D2 device, with Read,
  Off, Level 1 and Level 2. Only settings without filters are offered;
  filtered repeating needs filter lists (0x252) and is left out.
- `POST /api/gateway/recom-repeater/<name>`.

## Consequences

- Not yet confirmed on real hardware. If a module keeps a different value,
  the read back shows it and the UI says the value was not kept.
- Turning on level 2 in several modules close to each other multiplies
  radio traffic; the documentation recommends level 1.
