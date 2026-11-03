# 0044. New entity IDs come from the device name, the room is the suggested area

Status: proposed (v1.8.6-beta3).

## Context

Issue #64. Home Assistant's MQTT code no longer reads `object_id` (checked on
2026.12-dev), so the ID of a new entity was built from the area, the HA device
name and the entity name. That gave an unstable result: a device named after its
description, no area yet, and duplicates such as `light.spots_2`.

## Decision

- Send `default_entity_id` = `<component>.<object_id>` next to `object_id`, in
  one place after the configs are built. `object_id` stays for older versions.
- Send the room as `device.suggested_area`.
- Hardware model, serial number and a separate display name are not part of
  this. `description` stays the HA name (since 1.7.0, ADR-0043).

## Consequences

- New entity IDs are predictable and match the MQTT device name again, for
  example `light.woonkamer_spots` and `sensor.woonkamer_spots_rssi`.
- Existing entities keep their IDs: the registry wins. A deleted entity that is
  discovered again takes the default ID.
- `suggested_area` only acts at device creation in the checked HA version. It
  creates the area if it does not exist yet, so a typo in Room creates one.
