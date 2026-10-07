# 0022. Occupancy reads PIRS, under the old PIR key

Status: proposed (v1.8.4-beta7).

## Context

The default mappings for A5-07-01/02/03 and A5-08-01/02/03 named the occupancy
field `PIR`. The bundled EEP.xml decodes it as `PIRS` in every one of these
profiles, so the template `value_json.PIR` was always empty and the occupancy
binary_sensor never got a state. Nobody saw an error: HA skips an empty
binary_sensor payload. It came up when the Slim migration found no new entity
for a motion sensor's `presence` entity (forum post 49).

The meaning of PIRS differs per profile:

- A5-07-01: a value 0 to 255, 128 and up means motion.
- A5-07-02/03: 1 means motion.
- A5-08-0x: 0 means PIR on, 1 means off.

## Decision

- The mapping key stays `PIR`. The key is part of the unique_id, so renaming
  it would give every existing occupancy entity a new ID and leave the old one
  behind. Each mapping carries a `value_template` that reads `PIRS` and
  renders `1`/`0` for the profile's meaning, and nothing when a telegram has
  no PIRS, as before.
- The migration pairs by the field in the value_template, so it now sees
  `pirs` and pairs it with Slim's entity for the same field.

## Consequences

- Occupancy works for these profiles without any user action, and existing
  entity IDs stay.
- A user mapping override for these EEPs that copied the old `PIR` template
  stays broken until edited; overrides are not touched.
