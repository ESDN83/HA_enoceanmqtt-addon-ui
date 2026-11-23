# 0056. Encrypted sending

Status: proposed (beta).

## Context

Secure devices could only be received (ADR-0046). HA_enoceanmqtt 5.0.0 can
send as well.

## Decision

- The app generates a key and sends its own secure teach-in: three addressed
  telegrams, or two broadcast ones (the specification's split, too long to
  address). SLF 0x8B: RLC 3 bytes implicit, CMAC 3 bytes, VAES.
- Encryption sits in `_build_radio_packet`, where every transmit path ends.
  Only telegrams addressed to a device with a sending key; F6, UTE, SYS_EX
  and secure telegrams stay as they are.
- The next rolling code is saved before a telegram goes out. If that fails,
  nothing is sent.
- A previous receiving key is kept until the device uses the new one.
- No chaining: more than 5 data bytes are refused. D2-33-00 is left out.

## Consequences

- Verified against the vectors of the EnOcean security specification and by
  decrypting with OpenSSL. Not confirmed on hardware.
- A bidirectional teach-in from a device is not answered automatically.
- A restored old backup holds an old rolling code: send the key again.
