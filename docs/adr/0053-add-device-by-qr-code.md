# 0053. Add Device by QR code

Status: proposed (beta).

## Context

QR pairing (ADR-0047, 0051, 0052) works on real OPUS 563.010 and 563.076
(forum 1026367, 2026-11-13), but only from the page of a device that was
first entered by hand. The tester looked for it under Add Device. Both
devices needed the transceiver's Base ID as sender; a free ID did not work.

## Decision

- Add Device gets a fourth option, *QR Code*: name, QR label text, optional
  type and room. `POST /api/gateway/recom-add`.
- The address comes from the label (30S), the sender is the Base ID, the
  profile is the one in the device's ping answer. The role defaults from the
  profile: light for a D2-01 type that dims (ADR-0050), switch for the other
  D2-01 types, cover for D2-05.
- Pairing runs first; the device is created only after it succeeded, through
  the same create path as Manual Entry (validation, identity clash check,
  discovery). An address that is already configured is refused with a hint
  to pair from its page.
- The QR field is a password field and is cleared on submit; the code is
  used for the request only.

## Consequences

- A device that reports no profile in its ping answer cannot be added this
  way; Manual Entry plus pairing on its page still works.
- Multi-channel devices are added with channel 0 only.
