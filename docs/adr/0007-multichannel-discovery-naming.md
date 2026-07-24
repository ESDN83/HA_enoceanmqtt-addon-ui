# 0007. Multi-channel discovery naming and edit-path entity lifecycle

Status: accepted (v1.7.0-beta7). Refines ADR-0005.

## Context

Two channels of a D2-01 module share one address, so `build_device_info`
maps both to a single HA device (`identifiers = enocean_<address>`). The
discovery configs were published with the entity `name` left as `None`, which
makes HA fall back to the shared HA device name for every entity on that
device. The last channel published therefore set the name both channel
entities displayed, so both showed the same name (issue #34). ADR-0005 called
for "each entity uses its own configured device name" but that was never wired
up in the discovery builder.

The edit and delete paths made it worse:
- `update_device` re-published discovery **without** the `channel`, so a
  channel-1 device was recomputed under the channel-0 `unique_id`, and it
  **never retracted** the old configs. Any identity edit (address, sender,
  EEP, channel) orphaned the previous entities in HA.
- `channel` was missing from the update whitelist, so channel edits silently
  reverted.
- `delete_device` removed a channel's configs without the `channel` and
  without regard for a surviving sibling, so deleting one channel could strip
  the shared diagnostic sensors the other channel still needs.

## Decision

- **Naming.** When several devices share one address (a multi-channel
  module), the shared HA device carries a stable module label
  (`manufacturer + EEP model`, e.g. "NodOn D2-01-12") and each channel entity
  carries its own configured name (`description` or `name`). A single-address
  device keeps the previous behaviour (entity name `None` → HA device name),
  so single-channel devices are unchanged. See `_discovery_naming` in
  `api/devices.py` and the `module_name` argument of `build_device_info`.
- **Consistency across siblings.** create, update and delete are
  multi-channel aware and re-publish every device on the address, so adding,
  removing, or re-homing a channel updates the naming of the whole module (a
  2→1 transition drops the module label again).
- **Edit lifecycle.** `update_device` snapshots the pre-edit discovery
  configs and retracts (empty-payload removal, as in `delete_device`) any
  `unique_id` that no longer exists after the edit, so identity edits stop
  orphaning entities. `channel` is in the update whitelist. `delete_device`
  only retracts `unique_id`s that no surviving sibling still publishes, so a
  channel delete keeps the shared sensors of the remaining channel.

## Consequences

- Editing one channel no longer renames the other; identity edits no longer
  accumulate stale entities. Validated on a real HA (devcontainer with
  Supervisor + Mosquitto) by creating, editing, and deleting a D2-01-12
  channel pair and checking the resulting HA entities.
- The multi-channel HA device name is derived, not user-set. A dedicated
  module-name field could refine this later without changing this contract.
- `unique_id` still encodes the channel (ADR-0005), so changing an identity
  field legitimately produces a new entity; the old one is retracted rather
  than left behind.
