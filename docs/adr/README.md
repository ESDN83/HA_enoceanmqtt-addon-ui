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
