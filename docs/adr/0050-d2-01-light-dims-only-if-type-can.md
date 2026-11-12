# 0050. A D2-01 light gets brightness only if its type can dim

Status: proposed (beta).

## Context

A D2-01 module set up as `actuator_type: light` was always announced with
brightness. A relay such as the NodOn SIN-2-2-01 (D2-01-12) then showed a
0-100 % slider in Home Assistant that did nothing, and voice assistants
exposed it as dimmable (#73, arno0392). The telegram carries a dim value for
every type, so the layout does not tell whether a device can dim.

## Decision

The "Supported function ... of Type" table of the D2-01 specification
(EEP 2.6.8, page 3, checked against the PDF) marks dimming for the types 02,
03, 04, 05, 09 and 16 only. A D2-01 light of any other type is announced
without the brightness keys, the same way a light taught in on F6 already
was. It sends ON and OFF, which `send_d2_01_command` already handles.

## Consequences

- unique_id and entity_id do not change; the slider disappears after the
  discovery update.
- A device that dims on a profile of a switching type loses its slider. No
  per-device override is added until such a device turns up.
