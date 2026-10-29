# Architecture Decision Records

Short, immutable records of non-trivial decisions and the reasons behind them, so nobody re-litigates a choice or repeats a mistake. Format: context, decision, consequences.

Rules:
- One decision per file, numbered, never edited after acceptance. If a decision changes, add a new ADR that supersedes the old one and mark the old one Superseded.
- Add an ADR in the same change that makes the decision.
- Keep them short.

## Index

- [0001](0001-serial-port-device-selector.md) serial_port is a required device() selector
- [0002](0002-theme-detection-via-css-var.md) Theme detection reads HA's background CSS variable
- [0003](0003-eep-first-command-routing.md) Outbound command routing is EEP-first
- [0004](0004-beta-channel-and-forward-only-versioning.md) Beta channel and forward-only versioning
- [0005](0005-multichannel-device-model.md) Multi-channel actuator model
- [0006](0006-buildless-frontend.md) The frontend stays buildless
- [0007](0007-multichannel-discovery-naming.md) Multi-channel discovery naming and edit-path entity lifecycle
- [0008](0008-switch-state-feedback-and-echo.md) Switch state feedback: Eltako confirmation convention and commanded-state echo
- [0009](0009-device-name-as-key.md) The device name is a key, a topic and a URL segment at once
- [0010](0010-buildless-asset-loading.md) Loading the split frontend without a build step
- [0011](0011-availability-watchdog.md) Availability is opt-in per device, measured from last contact
- [0012](0012-serialized-transmit-and-command-queue.md) Serialized transmit path and an inbound command queue
- [0013](0013-rps-actuator-status-independent-of-eep-and-role.md) RPS actuator status is read independently of the configured EEP and role
- [0014](0014-eltako-shutter-feedback-and-stop.md) An Eltako shutter reports itself, and it is stopped by a tap
- [0015](0015-eltako-shutter-position-command.md) An Eltako shutter is driven to a position by time, after a second teach-in
- [0020](0020-import-from-slim-and-christophehd.md) Import the device list of Slim and ChristopheHD, and remove their old entities
- [0021](0021-reload-on-version-mismatch.md) The page reloads itself after an update
- [0022](0022-occupancy-reads-pirs.md) Occupancy reads PIRS, under the old PIR key
- [0023](0023-contact-meaning-and-sensor-invert.md) D5 contacts report open as on, and sensors can be inverted
- [0024](0024-window-handle-retired-fields-rssi.md) Window handles read CT, retired fields are cleared, RSSI from byte 5
- [0025](0025-mapping-audit-against-eep-xml.md) Default mappings are checked against EEP.xml
- [0026](0026-clear-stale-discovery-configs.md) Stale discovery configs are cleared at startup
- [0027](0027-bundled-profiles-overlay.md) Bundled profiles overlay, they are not copied
- [0028](0028-decode-direction-one-only.md) Received telegrams are decoded with direction 1 only
- [0029](0029-valves-answered-on-receive.md) Radiator valves are answered on receive
- [0030](0030-eep-families-share-a-layout.md) Missing D2-01 / D2-05 types use their family's layout; D2 actuators ignore rocker telegrams
- [0031](0031-base-image-and-dependencies.md) 64-bit only, base image Alpine 3.24, current libraries, paho-mqtt 2
- [0032](0032-vld-decode-by-command-pilot-wire.md) VLD telegrams decode by command; pilot wire modules are queried
- [0033](0033-ai-assistant-guide.md) AI assistants get a setup guide from the app itself
- [0034](0034-add-device-help-and-catalogue.md) The Add Device page explains itself, with a catalogue of verified devices
- [0035](0035-d2-01-metering.md) Every metering D2-01 module gets Power and Energy
- [0036](0036-free-sender-for-pairing-and-dimmer-confirmation.md) Pairing picks a free sender ID; a dimmer's confirmation keeps its level
- [0037](0037-f6-cover-stop-only-when-moving.md) A rocker-taught shutter is not sent Stop when it reported standing still
- [0038](0038-tcp-idle-keepalive-and-reconnect-wait.md) TCP idle keepalive, commands wait for a reconnect, own echoes ignored
- [0039](0039-meter-readings-need-confirmation.md) Implausible meter readings need a second reading
