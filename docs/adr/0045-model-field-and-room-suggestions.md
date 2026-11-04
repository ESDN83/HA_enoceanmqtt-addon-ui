# 0045. Model field, serial number and Room suggestions

Status: proposed (v1.8.6-beta4).

## Context

Issue #64. Description is the Home Assistant device name, so the hardware type
had no place of its own, and the device catalog put it in Description, naming
new devices after their hardware. A typo in Room creates a new area, because
Room is sent as `suggested_area` (ADR-0044).

## Decision

- New optional `model`. `device.model` = Model, or the profile when empty.
- `device.model_id` = profile, only when a Model is set. The reporter suggested
  always sending it, but without a Model Home Assistant would show the profile
  twice on every existing device.
- `device.serial_number` = address.
- The catalog fills in Model instead of Description.
- Room suggests areas through a `datalist`, read from Home Assistant through
  `GET /api/system/ha-areas`. Free text stays possible, the list is empty if
  Home Assistant cannot be reached.
- No Display name field: Description already is that.

## Consequences

- Existing devices gain a serial number in Home Assistant; names, IDs and the
  shown model do not change.
- A new device picked from the catalog without a Description is named after its
  device name in Home Assistant, not after its hardware.
- Two channels on one address share one HA device, so the channel saved last sets
  its model and serial number. Serial number is equal, Model should be too.
