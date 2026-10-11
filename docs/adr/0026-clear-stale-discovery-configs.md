# 0026. Stale discovery configs are cleared at startup

Status: proposed (v1.8.4-beta11). Supersedes the `RETIRED_FIELDS` part of
ADR-0024.

## Context

A retained MQTT discovery config outlives whatever produced it. Removing a
field in the mapping editor left its entity in Home Assistant forever
(sp00ky, forum post 59), and the mapping corrections of ADR-0024/0025 needed
a hand-kept list of retired fields to clear theirs. Device edits already
clear their own old configs; mapping changes take effect at the next start.

## Decision

After publishing all discovery configs at startup, the app reads the
retained configs and clears every one that:

- is under `<prefix>/<component>/enocean/<uid>/config` (this app's layout),
- has a unique_id `enocean_<eep6>_<addr8>_...` whose address belongs to a
  configured device,
- and was not published in this run.

If any device failed to publish, the cleanup is skipped, since its valid
configs would look stale. `RETIRED_FIELDS` is removed.

## Consequences

- Removed mapping fields, changed default mappings and changed EEPs no longer
  leave dead entities, and nobody has to remember to list them.
- Other apps' entities, the gateway diagnostics (`enocean_gateway_...`) and
  devices not configured here are never touched.
- Startup reads the retained configs once more, about three seconds.
