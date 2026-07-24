# 0001. serial_port is a required device() selector

Status: accepted (v1.6.2), reached after a painful back and forth (v1.6.0, v1.6.1).

## Context

Users asked to pick the EnOcean dongle from a list instead of typing a device path. The only thing that renders a live device list in the HA Configuration tab is the `device(subsystem=tty)` schema type. But Home Assistant cannot save or start a `device()` field that is empty ("Device '' does not exist"), and there is no portable default device (paths differ per machine and HA validates the default against the real device list).

Attempts and their failures:
- Optional `device()?` still rejects an empty value on save, breaking TCP-only setups (v1.6.0-beta2).
- Required `device()` blocked updates: existing installs with an empty stored value could not start until a device was picked (v1.6.0). A hotfix reverted to free text `str?` (v1.6.1), which lost the list.

## Decision

`serial_port` is a **required** `device(subsystem=tty)` selector. A device must be selected. `udev: true` is enabled so `/dev/serial/by-id/...` paths resolve inside the container. Because a TCP connection takes priority in `run.sh`, TCP-only users pick any device and it is ignored.

## Consequences

- After updating, users with no device selected must open Configuration and pick one. A prominent "action needed after updating" note goes at the top of the CHANGELOG (HA shows it in the update dialog).
- A machine with no tty device at all cannot save the config even for TCP-only use. This is a Home Assistant platform limitation; HAOS always lists the on-board serial ports, so it is an edge case.
- Do not silently switch this back to `str?` without asking. See the memory note on this tradeoff.
