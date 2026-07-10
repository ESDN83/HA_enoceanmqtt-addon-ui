# Fork Integration & Optimization Plan

**Status:** Analysis complete — execution pending
**Created:** 2026-07-09 (session with limited budget; plan written to survive context loss)
**Executor note:** This plan is self-contained. Any model (e.g. Sonnet) can execute it without the original session. Work happens on `addon-beta/` (beta channel) first, never directly on `addon/` (stable).

---

## 1. Context / Current State

- **Repo:** `ESDN83/HA_enoceanmqtt-addon-ui` — HA add-on repository with two add-ons:
  - `addon/` — **stable**, v1.4.0 (field-tested D2-05/D2-01/UTE/invert, issue #2 work merged)
  - `addon-beta/` — **beta channel**, v1.4.0-beta4, `slug: enocean-mqtt-ui-beta`, `stage: experimental`
- **Fork analyzed:** `arno0392/HA_enoceanmqtt-addon-ui` (`fork/main` remote already added locally).
  Fork branched at v1.2.5 (merge-base `429648d`), is 50 commits ahead / 14 behind, self-versioned "1.4.2".
- Open PRs: none. Issues #1/#3 closed (v1.3.0), #2 in field-testing via beta channel with @EricGIRARD35.

## 2. Fork Analysis Results (done)

### 2.1 EEP profile library — **PORT THIS** ⭐
Fork expanded `DEFAULT_MAPPINGS` in `addon/rootfs/app/core/mapping_manager.py` from 9 → 71 profiles.
**62 profiles exist only in the fork** (verified by set comparison):

```
A5-02-01..0B, A5-02-10..1B, A5-02-20, A5-02-30          (full temperature family)
A5-04-02 A5-04-03                                        (temp+humidity)
A5-06-01                                                 (light sensor)
A5-07-02 A5-07-03                                        (occupancy)
A5-08-01 A5-08-02 A5-08-03                               (light/temp/occupancy combos)
A5-09-02 A5-09-04 A5-09-05                               (CO2, CO2+T+H, VOC)
A5-10-01 A5-10-06                                        (HVAC thermostat)
A5-12-01 A5-12-02 A5-12-03                               (meters: electricity/gas/water, with state_class total_increasing)
A5-14-01 A5-14-05 A5-14-09 A5-14-0A                      (vibration/window/illuminance)
A5-30-01 A5-30-02                                        (digital input)
D2-01-01 D2-01-02 D2-01-06 D2-01-08..0E D2-01-11 D2-01-12  (electronic switches; 11=2ch dimmer, 12=2ch switch)
D2-05-01                                                 (blinds variant)
F6-03-01 F6-03-02 F6-10-00                               (4-rocker, window handle)
```

Quality check (samples reviewed): proper `device_class`, `unit_of_measurement`, `state_class` — good quality.
**Do NOT take fork's F6-02-01/F6-02-02** — ours is better (per-button binary_sensors AI/AO/BI/BO from v1.3.0; fork only has text sensors).
**Source of truth:** `git show fork/main:addon/rootfs/app/core/mapping_manager.py`

### 2.2 Multichannel state merge — **PORT THIS**
`mqtt_handler.py` fork adds `_merge_multichannel_state()` (+ `self._multichannel_eeps` map + `self._channel_cache`):
for D2-01-11/12 (2-channel devices) it uses the `IO` field as channel discriminator and merges the cached other-channel
value into every publish (e.g. `OV_CH1`), so one channel update doesn't wipe the other in HA.
Pairs with the D2-01-12 profile (`OV` = channel 0, `OV_CH1` = channel 1 binary_sensors).
Called from `publish_state()` before caching. Fork changelog notes channel-1 payload "to be confirmed" → mark as beta feature.
**Source:** `git show fork/main:addon/rootfs/app/core/mqtt_handler.py` (search `_merge_multichannel_state`).

### 2.3 MQTT config via Web UI — **PORT THIS (adapted)**
Fork lets users edit MQTT broker settings in the web UI (not just HA add-on config panel):
- `api/system.py`: `GET/POST /api/system/mqtt-config` + `_read_options()/_write_options()` writing `/data/options.json`
- `main.py`: `_load_mqtt_config()` reads options.json at startup
- `run.sh`: `_opt_value()` jq helper; priority: UI-saved options.json → config.yaml options → bashio services
- `index.html`: small settings panel (~2 references `mqtt-config`)

**Adaptation needed:** our `run.sh` (since v1.3.0) already has priority `config.yaml mqtt.host → bashio services`.
Fork uses different option key names (`mqtt.mqtt_host` vs our `mqtt.host`) — **normalize to our names** (`mqtt.host/port/username/password`).
Careful: writing `/data/options.json` from inside the addon is unusual but works; validate JSON before write, keep backup of previous file.

### 2.4 UI rework — **RESOLVED 2026-07-10: nothing to merge**
Detailed review done: fork `index.html` (2972 lines) vs common base 1.2.5 (3526 lines) differs by only
−4,882 chars (−2.5%). Function inventory diff shows **zero removed/refactored functions** — the fork only
(a) reformatted (fewer blank lines: 311→201, longer lines: avg 54.5→63.1 chars) and (b) added 4 MQTT-broker
panel functions (`mqttBrokerLoad/Save`, badge/alert helpers, no reset capability).
Verdict: no genuine code optimizations exist; reformatting would create huge diffs for zero benefit.
The MQTT panel idea was implemented independently (better: Reset to Defaults + Supervisor self-restart)
in beta 1.5.0-beta2. **This work item is closed.**

### 2.5 Not portable / skip
- Fork's external-MQTT implementation (we have our own since v1.3.0; fork's differs in option names)
- Fork's F6-02-02 (ours is better)
- Fork's version/CHANGELOG/README/repository.json edits (fork-specific identity, would clash)
- Fork is 14 commits behind: lacks our D2-05/D2-01/UTE/invert fixes, beta channel, app_version.py

## 3. Execution Plan (beta channel first)

### Step A — Port 62 EEP profiles → `addon-beta/`  [Task #2]
1. Branch from main: `feature/fork-eep-profiles`
2. Extract fork `DEFAULT_MAPPINGS`: `git show fork/main:addon/rootfs/app/core/mapping_manager.py`
3. Add the 62 new profiles to `addon-beta/rootfs/app/core/mapping_manager.py` DEFAULT_MAPPINGS.
   Keep our existing 9 entries as-is (esp. F6-02-01/02 with `_rocker_button_binary_sensors()`).
   Keep dict ordered by EEP family for readability.
4. Sanity: `python -m py_compile`, quick import-free exec check of DEFAULT_MAPPINGS structure
   (each entry: component + name; value_template syntax `{{ ... }}` balanced).
5. Bump `addon-beta/config.yaml` version (next beta, e.g. 1.5.0-beta1 — decide vs current beta4 numbering),
   CHANGELOG entry crediting @arno0392.
6. PR → main. (Beta only; stable `addon/` untouched.)

### Step B — Port multichannel merge → `addon-beta/`  [Task #2/#3]
1. Same or follow-up branch. Copy `_merge_multichannel_state`, `_multichannel_eeps`, `_channel_cache`
   from fork `mqtt_handler.py` into `addon-beta/.../mqtt_handler.py`; call from `publish_state()`.
2. Only wire for D2-01-11/12 initially. CHANGELOG: mark experimental (channel-1 payload unconfirmed upstream).

### Step C — MQTT config via UI → `addon-beta/`  [Task #3]
1. Branch `feature/ui-mqtt-config`. Port `GET/POST /api/system/mqtt-config` endpoints (normalize option keys to
   `mqtt.host/port/username/password`), `_load_mqtt_config()` in main.py, `_opt_value()` priority block in run.sh
   (insert as source 1 above our existing config.yaml/bashio logic), settings panel in index.html.
2. Security: POST validates types; password write-only in UI (return masked on GET).
3. Beta CHANGELOG + version bump; PR → main.

### Step D — Field test via beta channel, then promote to stable
1. Beta users test (store: "EnOcean MQTT UI (Beta)").
2. When confirmed: copy changes `addon-beta/` → `addon/`, version 1.5.0 stable, CHANGELOG, release + GitHub release.
   (Reminder from memory: ALWAYS bump `addon/config.yaml` version + CHANGELOG together, store serves main.)

### Step E — Notify @arno0392  [Task #5]
After A (+B/C) merged: open an issue in `arno0392/HA_enoceanmqtt-addon-ui` (fork has no upstream-issue rights needed):
thank for the 62-profile library + multichannel merge + UI-config idea, note they were integrated upstream with credit
in CHANGELOG, point out fork is 14+ commits behind (missing D2-05 VLD covers, UTE teach-in, invert, beta channel,
external MQTT via config panel), invite future contributions as PRs against upstream. Friendly tone; EN or FR/DE.

### Step F — Optional cleanups (backlog, low priority)
- Local branch cleanup: `git branch -d chore/beta-addon-channel chore/beta-experimental-stage feature/f6-02-02-and-external-mqtt` (merged; safe). Unknown local branches `exciting-nightingale`, `festive-austin`, `loving-hodgkin` — inspect before deleting.
- Remove stale remote branches: `fix/*`, `release/stable-1.4.0`, `test/d2-05-00-cover` (all merged into main per v1.4.0).
- `.pyc`/`__pycache__` not tracked — OK. `addon/rootfs/app/api/__pycache__` exists locally only.
- Issue #2: still open pending @EricGIRARD35 feedback on beta; position feedback (D2-05 CMD 4 decode) still TODO.
- Consider deduplicating `addon/` vs `addon-beta/` maintenance burden later (e.g. sync script or build step).

## 4. Verification checklist per step
- [ ] `python -m py_compile` on every touched .py
- [ ] `python -c "import yaml; yaml.safe_load(open('addon-beta/config.yaml'))"`
- [ ] `bash -n addon-beta/rootfs/run.sh`
- [ ] Version bumped in `addon-beta/config.yaml` AND `rootfs/app/main.py` (check whether beta now uses `app_version.py` — stable does since 1.4.0!)
- [ ] CHANGELOG.md entry with fork credit
- [ ] PR to main, merge, then `ha store reload` to surface in store
