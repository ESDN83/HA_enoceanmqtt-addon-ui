# 0020. Import the device list of Slim and ChristopheHD enocean-mqtt

Status: proposed (v1.8.4-beta3, amended in v1.8.4-beta5).

## Context

People switch from two add-ons: ChristopheHD's enocean-mqtt and our own
archived EnOcean MQTT Slim. A forum user with many sensors on Slim asked how
to switch without redoing everything. Nothing carried over:

- DOCS.md claimed the old `enoceanmqtt.devices` could be imported from the
  Settings page. It could not: the ZIP import reads only this app's own files,
  and the INI loader runs only for a file in `/data`, where no user can put one.
- Slim keeps `{address: {id, name, eep}}` in its own `/data/devices.json`. A
  different slug means a different `/data`, and Slim has no export.
- Entity unique IDs differ (Slim `enocean_<addr>_<field>`, here
  `enocean_<eep>_<addr>_<field>`), and so do the MQTT topics.

## Decision

A Settings card reads an old device list and shows it for review. It does not
write anything itself.

- ChristopheHD: read `/config/enoceanmqtt.devices` directly (`config:rw` is
  already mapped), or an uploaded copy. Sections with `ignore`, only `model =`,
  or no valid address are listed as skipped with the reason.
- Slim: find it through the Supervisor (`GET /addons`, slug ending in
  `enocean-mqtt-slim`, then its `ip_address` and `ingress_port`) and fetch its
  own `GET /api/devices`. Slim must be running. An uploaded `devices.json` or
  saved `/api/devices` response works too.
- The format of an upload is told by content (JSON vs INI), not by file name.
- Each candidate is marked `exists` (same address and EEP already configured)
  and `eep_known`, and gets a free, topic-safe name. Those are unticked.
- Every chosen device goes through the normal `POST /api/devices`, so name
  checks and discovery publishing are not duplicated.

Entities are new: keeping the old unique IDs would need a per-device ID
scheme, and a mistake there breaks HA history. Instead a second step removes
the old entities:

- Both old apps publish discovery at `<prefix>/<component>/<unique_id>/config`
  (three levels); this app at `<prefix>/<component>/enocean/<uid>/config`
  (four). A short-lived MQTT client of its own reads the retained three-level
  configs, so our own topics can never match.
- An entry is offered only if its `unique_id` starts with `enocean_` and
  carries the address of a device configured here, so nothing is removed
  before its device exists in this app.
- Removal publishes an empty retained payload; HA then drops exactly those
  entities. The HA device is not deleted. Slim shares our device identifier
  (`enocean_<addr>`), so the device keeps the new entities. ChristopheHD's
  device (identifier `<ADDR>`) is separate and HA drops it once empty.
- The server re-checks every topic it is asked to clear against the same
  rule and refuses while Slim is running, which would republish them.
- The help popup and all strings exist in all 11 languages.

## Amendment (v1.8.4-beta5): keep the old entity IDs

Users asked how to get their old entity IDs back. Step 2 now does it:

- Every entity, old and new, gets a field key: the field its
  `value_template` reads (`value_json.TMP` gives `tmp`), else the unique_id
  after the address. ChristopheHD's `_RSSI_`/`_DATE_` map to `rssi`/
  `last_seen`. The apps name entities differently (Slim `..._TMP`,
  ChristopheHD `tempC`), but all read the same decoded telegram.
- A pair needs the same address, key and component (the domain is part of
  an entity ID). ChristopheHD's raw/rounded twins resolve to the rounded one;
  anything still ambiguous, or of another type (Slim's D5 `sensor` vs our
  `binary_sensor`), is shown for renaming by hand.
- Entity IDs come from the entity registry over the WebSocket API
  (`ws://supervisor/core/websocket`, `homeassistant_api`). After the old
  configs are cleared, the rename waits until HA has dropped the old entities,
  then calls `config/entity_registry/update` with `new_entity_id`.
- The recorder cannot migrate the new entity's few hours of history onto an
  ID that already has history, so the new entity simply continues the old
  entity's history under that ID. Verified in the devcontainer.
- If the old app comes back after a migration, HA recreates its entities as
  `<id>_2`. Those are not renamed onto ours (marked "already has this ID").
- Without the registry (WebSocket unreachable), removal still works and the
  IDs are left for renaming by hand.

## Consequences

- `model =` devices (ChristopheHD brand configs) are not mapped to an EEP; the
  user adds them by hand.
- Actuators come in without `actuator_type`; the UI says to check them.
- Slim is found by slug (`4b60c4f5_` is the store's hash of its GitHub URL,
  or `local_`): the default Supervisor role may read one add-on's info but
  not list them (403).
- The ChristopheHD cleanup was tested against discovery messages built to its
  source (`HA_enoceanmqtt` develop, `ha_communicator.py`), not a running
  ChristopheHD app.
- The wrong migration section in DOCS.md is replaced.
- Entity IDs are looked up by (domain, unique_id), not unique_id alone: an
  entity once published as a sensor and later as a binary_sensor leaves two
  registry entries with one unique_id, and picking the wrong one made the
  rename fail with "New entity ID should be same domain" (beta7, forum post 49).
