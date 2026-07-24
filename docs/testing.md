# Testing

The only real test is the add-on running inside a real Home Assistant. Everything below is ordered from "closest to production" to "quick local sanity check". Do not treat the local checks as QA.

## 1. Devcontainer with a real Supervisor (recommended for development)

Home Assistant's official add-on development method is a VS Code devcontainer that boots a full Supervisor plus Home Assistant. This repo ships it: `.devcontainer/devcontainer.json` and `.vscode/tasks.json`. Both `addon/` and `addon-beta/` appear automatically under "Local Apps".

Run it on a Linux host with Docker, not on Windows. A dedicated VM (for example Debian in VirtualBox) is the clean choice.

Debian VM setup, once:
1. Install Docker Engine and Git. Add your user to the `docker` group.
2. Install VS Code with the "Dev Containers" extension. Either run VS Code on the VM directly, or use VS Code on your workstation with the "Remote - SSH" extension to open the repo on the VM, then "Reopen in Container".
3. Clone this repo on the VM and open it in the devcontainer.

Each session:
1. Open the repo in the container.
2. Run the "Start Home Assistant" task (it runs `supervisor_run`).
3. Open `http://localhost:7123/` (mapped from the container's 8123), finish onboarding once.
4. The add-on appears under Settings, Add-ons, Local Apps. Install it, set a serial or TCP port, and test with real Ingress, MQTT, and theme.

Reference: https://developers.home-assistant.io/docs/add-ons/testing

## 2. Beta channel on a real Home Assistant (current QA path)

The `addon-beta/` add-on (`enocean-mqtt-ui-beta`) is published from this repo. Install it on a real HA instance (the maintainer's HA, or a dedicated test instance) and on field testers' hardware. This is what actually validates serial/TCP transport, teach-in, MQTT discovery, Ingress, and theme against a real HA parent. New work is field tested here before promotion to stable.

## 3. Backend sanity checks (fast, not QA)

- `python -m py_compile` on changed Python files.
- Parse checks: `yaml.safe_load(config.yaml)`, JSON parse of i18n files.
- Direct module import test for pure logic (for example `mapping_manager.get_ha_discovery_configs`), loading the single module to avoid the package's heavy imports.

## 4. Frontend logic pre-check (throwaway, not QA)

For pure CSS/JS logic (theme detection, form reset, dialogs) you can load `templates/index.html` inside an iframe whose parent mimics HA's CSS variables, and assert computed styles via a small script. This catches obvious regressions cheaply, but it is not a substitute for testing in real HA: it cannot validate Ingress, MQTT, serial, or the actual HA theme cascade. Use it as a smoke test only. It was how ADR-0002 was reproduced. Note that HA's parent body is transparent, so the harness parent must also have a transparent body to be representative.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request to `main`:
- hadolint on all Dockerfiles (config in `.hadolint.yaml`),
- shellcheck on shell scripts,
- YAML validation of the `config.yaml`/`build.yaml` files, JSON validation of the i18n files, and `compileall` of the Python app,
- a build smoke test that builds both add-on images for amd64 (no push), catching Dockerfile and dependency breakage.

## Possible follow-ups

- Multi-arch image publishing to ghcr via `home-assistant/builder`, if the project ever moves from build-on-install to prebuilt images. That changes the distribution model and needs `config.yaml` to reference the published image, so it is a deliberate decision, not a lint step.
