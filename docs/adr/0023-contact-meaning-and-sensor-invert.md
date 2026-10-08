# 0023. D5 contacts report open as on, and sensors can be inverted

Status: proposed (v1.8.4-beta8).

## Context

EEP.xml defines D5-00-01 CO as 0 = open, 1 = closed. The default mapping sent
CO as-is with `payload_on: "1"`, and a `door` binary_sensor reads on as open,
so every D5 contact showed open when closed and the other way round. Found by
Kohhal against the app's own decoded `CO: closed 0x09` (forum post 51).

That is the second profile in a week whose meaning the mapping had wrong
(ADR-0022). A per-device way out is wanted in case a fix like these is wrong
for some device, or a contact is mounted the other way.

## Decision

- D5-00-01 keeps its `CO` key (entity IDs stay) and gets a value_template
  `1 - CO`, so on means open.
- `invert`, so far only for covers and switches, now also applies to sensor
  devices: it swaps `payload_on` and `payload_off` of every binary_sensor of
  that device. The form shows it for the sensor role.
- Swapping the payloads, not the template, keeps it independent of the
  mapping: it also works with a mapping override or a custom profile.

## Consequences

- D5 contacts show the right state after the update, without user action.
  Automations written against the inverted state have to be checked.
- A sensor device with buttons (F6) inverted would show its buttons as
  pressed while released; the option is meant for contacts and occupancy.
- Only English and German carry the new label; the other languages fall back
  to English, like the existing invert labels.
