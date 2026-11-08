# 0046. Profiles, blueprints and secure telegrams without a tester

Status: proposed (v1.8.7-beta2).

## Context

Issues #57, #59, #60, #61, #62 collected wishes from the forum and other
integrations. No tester has the hardware. The owner decided to build them
from the specifications and cross-checked implementations, with fixtures and
the fake transceiver, and to let field reports correct them.

## Decision

- **Valves A5-20-04 / -06** reuse the A5-20-01 answer mechanism
  (ADR-0029), with their own reply bytes from EEP.xml direction 2. Scaling
  checked against FHEM and, for -04, openHAB. They disagree on one bit:
  FHEM sets DB1.7 on A5-20-04 when the valve is to regulate to the
  temperature itself, openHAB never does. We follow FHEM in temperature mode.
- **D2-14-30 / -41** get default mappings; EEP.xml scales the values already.
- **D2-50** gets per-type mappings from EEP.xml, a mode select and a status
  request (FHEM's byte layout), and its state is merged across the basic and
  extended status. The VLD decoder now also selects layouts by an `MT` field.
- **Blueprints** are bundled files, offered only for matching devices and
  saved through `blueprint/save` on request; an existing one is never
  overwritten. `source_url` points at the stable tree.
- **Secure telegrams**: receive only, VAES with CMAC and RLC, no PSK. AES-128
  is implemented in the app (checked against FIPS-197 and RFC 4493 vectors)
  instead of adding a native library. Teach-in is accepted only during a
  teach-in session or for a configured address. Keys live in
  `secure_devices.yaml` (mode 600), never in the log, and go with the device.

## Consequences

- None of it is confirmed on hardware; the docs say so and no catalog entry
  is made (ADR-0034).
- A secure key is not in backups: after a restore a secure device needs a new
  teach-in.
- Existing A5-20-04/-06 devices change entities: the generic EEP.xml
  entities give way to the new mapping.
