# 0036. Pairing picks a free sender ID; a dimmer's confirmation keeps its level

Status: proposed (v1.8.5-beta12).

## Context

Forum post 84 (a migration from IP-Symcon with a FAM14, FSR14-4x, FUD14,
FSB61 clones and a NodOn plug):

- Every D2 module paired by UTE was told to bind base ID + 1. The first
  Eltako actuator taught with offset 1 used the same sender, and Eltako
  actuators act on a sender ID whatever the destination: switching the plug
  could switch the FSR14 channel.
- A FUD14 set to 50 % showed 100 % as soon as its confirmation arrived. The
  FAM14 confirms Eltako dimmers with a rocker telegram, on or off, and
  ADR-0013 set a light's brightness to 100 or 0 from it, which is only
  right for a relay.

## Decision

- A UTE or valve teach-in response uses the device's own sender ID if it is
  configured, else the lowest gateway offset (1..127) that no device uses.
  An offset handed out to a module not saved yet is reserved by its address
  until restart, so two modules paired in a row do not share one. The valve
  teach-in (ADR-0029) uses the same rule; it started at offset 2 before.
- A rocker confirmation on a light whose profile is not F6 sets the state;
  on keeps the last brightness (100 if none is known), off sets 0. A light
  on an F6 profile keeps 100 / 0.

## Consequences

- Modules paired before keep their sender ID; only new pairings change.
- The Actuator Teach-In still uses the offset the user picks; the dialog
  suggests the next free one.
