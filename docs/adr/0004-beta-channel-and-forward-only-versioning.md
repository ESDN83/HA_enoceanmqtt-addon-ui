# 0004. Beta channel and forward-only versioning

Status: accepted (v1.3.0 for the beta channel, reinforced at v1.6.2).

## Context

The HA store serves the version in `config.yaml` on the repository's default branch. There is no built-in way to point the store at a non-default branch, and GitHub pre-releases are not installable as add-on versions. Shipping unfinished work straight to stable burned users twice (the v1.6.0/v1.6.1 serial-port churn).

Home Assistant only offers updates to a **higher** version. A lower version is never offered as a downgrade, and deleting a GitHub release does not change what is installed on a user's machine.

## Decision

- Maintain a second add-on `addon-beta/` in the same repo (slug `enocean-mqtt-ui-beta`, `stage: experimental`). New work lands there first and is field tested on real HA before promotion.
- Promote by copying the changed files from `addon-beta/` to `addon/`, bumping both `config.yaml` versions and CHANGELOGs, and cutting a `vX.Y.Z` GitHub release.
- Versions move forward only. To fix a bad release, always bump up. Never rely on a downgrade or on deleting a release to reach already-updated users.
- `app_version.py` reads the version from `config.yaml` at runtime; do not hardcode versions elsewhere.

## Consequences

- Stable stays clean; experiments are visible only to those who opt into the beta.
- A prominent CHANGELOG note is the channel for post-update user action (HA shows it in the update dialog).
- History cleanups (squash, deleting old releases) are cosmetic and must never lower the served version.
