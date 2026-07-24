# Testing

The only real test is the add-on running inside a real Home Assistant. Everything below is ordered from "closest to production" to "quick local sanity check". Do not treat the local checks as QA.

## 1. Devcontainer with a real Supervisor (recommended for development)

Home Assistant's official add-on development method is a VS Code devcontainer that boots a full Supervisor plus Home Assistant at `http://localhost:7123/`. The add-on in the repo root shows up automatically under "Local Apps" and can be installed and tested there, with real Ingress, MQTT, and theme behavior.

This repo does not ship a `.devcontainer` yet. Adding one is a tracked improvement (see the TODO at the bottom). Reference: https://developers.home-assistant.io/docs/add-ons/testing

## 2. Beta channel on a real Home Assistant (current QA path)

The `addon-beta/` add-on (`enocean-mqtt-ui-beta`) is published from this repo. Install it on a real HA instance (the maintainer's HA, or a dedicated test instance) and on field testers' hardware. This is what actually validates serial/TCP transport, teach-in, MQTT discovery, Ingress, and theme against a real HA parent. New work is field tested here before promotion to stable.

## 3. Backend sanity checks (fast, not QA)

- `python -m py_compile` on changed Python files.
- Parse checks: `yaml.safe_load(config.yaml)`, JSON parse of i18n files.
- Direct module import test for pure logic (for example `mapping_manager.get_ha_discovery_configs`), loading the single module to avoid the package's heavy imports.

## 4. Frontend logic pre-check (throwaway, not QA)

For pure CSS/JS logic (theme detection, form reset, dialogs) you can load `templates/index.html` inside an iframe whose parent mimics HA's CSS variables, and assert computed styles via a small script. This catches obvious regressions cheaply, but it is not a substitute for testing in real HA: it cannot validate Ingress, MQTT, serial, or the actual HA theme cascade. Use it as a smoke test only. It was how ADR-0002 was reproduced. Note that HA's parent body is transparent, so the harness parent must also have a transparent body to be representative.

## TODO to reach best practice

- Add a `.devcontainer` so contributors get a real Supervisor locally (item 1).
- Add CI (GitHub Actions) that at least lints (hadolint, shellcheck, yamllint) and builds the add-on image for the supported arches, matching the community add-on standard.
