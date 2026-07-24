# Project context for AI assistants and developers

Read this first. It is the entry point. Deeper detail lives in `docs/`. Keep this file lean; put details in `docs/` and link to them.

## What this is

A Home Assistant add-on ("app") that bridges EnOcean radio devices to MQTT with a web UI for visual device configuration, EEP profile editing, and HA MQTT discovery. It has its own ESP3 serial stack (it does not depend on the ChristopheHD/kipe enocean Python library at runtime; only the bundled `EEP.xml` comes from there).

## Repository layout

- `addon/` the stable add-on (what most users install). `config.yaml` version is what the HA store serves.
- `addon-beta/` a second add-on published from the same repo (slug `enocean-mqtt-ui-beta`, `stage: experimental`). New work lands here first for field testing, then is promoted to `addon/`.
- `addon*/rootfs/app/` the application:
  - `main.py` FastAPI app, lifespan, MQTT command routing (`_handle_device_command`), discovery publishing.
  - `core/` domain logic: `serial_handler` (ESP3 send/receive, teach-in), `mqtt_handler`, `device_manager`, `eep_manager`, `mapping_manager` (HA discovery configs, `DEFAULT_MAPPINGS`), `telegram_buffer`.
  - `api/` FastAPI routers: `devices`, `eep`, `mappings`, `system`, `gateway`.
  - `templates/index.html` the entire web UI in one file (HTML + inline CSS + inline JS). This is a known structural problem, see `docs/FRONTEND_REFACTOR_PLAN.md`.
  - `static/` served at `/static`; `data/EEP.xml` the bundled profile database.
  - `run.sh` reads add-on options via bashio and starts the app.
- `docs/` architecture, testing, decision records, and refactor plans.

## Data flow

Inbound (device to HA): `serial_handler` parses ESP3 packets into a `RadioTelegram`, `_process_telegram` decodes it with the device's EEP profile (`eep_manager`), and publishes state via `mqtt_handler` to every device configured on that address. Teach-in is handled separately (UTE for D2, LRN bit for A5/D5).

Outbound (HA to device): an MQTT command on `enoceanmqtt/<device>/set` reaches `_handle_device_command` in `main.py`, which routes **by EEP first** (D2-01, D2-05) and only then by role (light, switch, cover). It calls the matching `serial_handler.send_*`. See ADR-0003.

MQTT: HA discovery configs come from `mapping_manager.get_ha_discovery_configs`. Topics: `enoceanmqtt/<device>/state|set`, discovery `homeassistant/<component>/enocean/<uid>/config`.

## Run and test

The real test path is a running Home Assistant, not local mocks. See `docs/testing.md` (devcontainer with a real Supervisor, plus the beta add-on channel on a real HA instance).

## Release process

- The store reads `config.yaml` `version:` on the **default branch (`main`)**. A change is invisible until merged.
- Versions move **forward only**. You cannot fix a bad release with a lower version; HA never offers a downgrade. Deleting a GitHub release does not downgrade installed instances.
- `app_version.py` reads the version from `config.yaml` at runtime, so do not hardcode a version in `main.py`/`api`.
- Flow: land in `addon-beta/` (bump `addon-beta/config.yaml` and its `CHANGELOG.md`), field test, then promote by copying the changed files to `addon/`, bump `addon/config.yaml` + `CHANGELOG.md`, cut a `vX.Y.Z` GitHub release. Bump both trees together when touching stable.

## Key decisions (see docs/adr)

- `serial_port` is a required `device(subsystem=tty)` selector, not free text. ADR-0001.
- Theme detection reads HA's `--primary-background-color` variable, never the parent body background. ADR-0002.
- Outbound command routing is EEP-first. ADR-0003.
- Beta channel model and forward-only versioning. ADR-0004.
- Two-channel modules share one address and sender; the channel is carried in the command IO field, the discovery `unique_id`, and the entity name. ADR-0005.
- The frontend is intentionally buildless (no bundler); split it into files without introducing a build step. ADR-0006 and `docs/FRONTEND_REFACTOR_PLAN.md`.

## Conventions

- Beta first. Do not change stable `addon/` behavior without a beta and confirmation.
- Validate UI and protocol changes before release. Do not assume; check against the spec or a second implementation, and test on a real HA. ADR-0002 and ADR-0003 both came from wrong assumptions.
- Record every non-trivial decision as a short ADR in the same change (`docs/adr/`).
