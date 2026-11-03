# 0043. Restore replaces, and one identity is one device

Status: proposed (v1.8.6-beta2).

## Context

Issue #63. A restore wrote the backup's devices.yaml and reloaded it, but the
loader added to the dict in memory instead of replacing it. Devices renamed
after the backup survived next to their old names, the next save wrote both
back, and two devices claimed the same `unique_id`s. Whichever published last
owned the HA entities, while received telegrams went to the other one.

Issue #64 asked for a Home Assistant name apart from the device key, because
HA 2026.11 prefixes new entity IDs with the area and the room was in the key.

## Decision

- Loading devices.yaml replaces the device dict. A restore or import gives
  back exactly the backup, no merge mode.
- Identity is address, sender, EEP and channel, the inputs of every
  `unique_id`. Create and edit refuse a second device with the same identity
  (400). Duplicates already on disk are not deleted (we never delete devices
  on our own, see migration rules), only named: in the restore and import
  response (`details.duplicates`), as a UI warning, and in the log at load.
- No new name field. `description` already is the HA device name
  (`build_device_info`, falls back to the key). The field now says so.
  Stripping the room automatically was rejected: it would rename existing HA
  devices on update.

## Consequences

- A restore of an old backup drops devices added since. DOCS says to take a
  fresh backup first.
- Two devices on one address stay possible when they differ in channel or
  sender, which two-channel modules and multi-sender actuators need.
