# 0054. Secure PTM switches: translate the D2-03-00 code to RPS

Status: proposed (beta).

## Context

A secure PTM 210 (#62, butonche, 2026-11-15) was taught in correctly and
its telegrams verified, but every press decoded as "released": the
decrypted byte was 0x0C, fed to the F6-02-01 profile as if it were an RPS
byte. A PTM in secure mode (teach-in TYPE = switch, RORG 0x30) carries a
4-bit code: the D2-03-00 values FHEM decodes as subType switch.00 (14 A0,
13 AI, 12 B0, 11 BI, 7/10/5/9 two buttons, 8 energy bow only, 6 three or
four buttons, 15 released).

## Decision

- For a 0x30 telegram from a device taught in as a switch and configured
  with an F6 profile, translate the code into the F6-02 data byte and status
  (T21, NU) an unencrypted PTM would send. The configured rocker profile,
  its entities and the rocker events then work unchanged.
- An unknown code is dropped with a debug line.
- The radiator valve role (#60) is handled separately: a valve's role is
  stored empty and ignored in discovery.

## Consequences

- Users keep configuring a secure PTM as F6-02-01/02, as for a plain one.
- Not covered: D2-03-00 configured directly as the device profile (not in
  the bundled EEP.xml).
