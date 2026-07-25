---
name: devcontainer-testing
description: Run and test this add-on against the real Home Assistant devcontainer on this machine. Use whenever a change needs verifying on real HA, when the test stack is down after a reboot, when add-on install or rebuild fails, or when entities look wrong in HA. Covers bring-up, fast deploy, test fixtures, and the environment traps that otherwise cost an hour.
---

# Testing against the devcontainer HA

The real test path is a running Home Assistant, not local mocks. Everything
here is scripted under `scripts/devcontainer/`. **Run the scripts, do not
re-derive the commands.** Each one is short and readable if you need detail.

```bash
scripts/devcontainer/status.sh     # what is up, what is broken (start here)
scripts/devcontainer/up.sh         # cold start after a host reboot
scripts/devcontainer/deploy.sh     # copy changed app files in, restart, seconds
scripts/devcontainer/fixtures.sh   # one test device per discovery path
scripts/devcontainer/seed-states.sh # give devices a state
scripts/devcontainer/rebuild.sh    # build the real image, before releasing
```

Typical loop: `status.sh`, edit code, `deploy.sh`, check in HA, and
`rebuild.sh` once before a release.

`ha-mcp` tools talk to this HA directly (`ha_get_state`, `ha_search`,
`ha_get_device`, `ha_manage_addon`). Prefer them over shell for reading HA
state. `ha_manage_addon` with `path=/api/...` proxies into the add-on's own
API, which is the quickest way to create or edit devices.

## Read this before debugging what you see in HA

**Two on/off buttons instead of a toggle** has two causes, and they look
identical. Either the entity is marked `assumed_state` (the discovery config
was `optimistic`), or its state is `unknown`. Without a dongle nothing ever
publishes, so everything sits at unknown. Run `seed-states.sh` first, then
judge. Check the real cause with `ha_get_state` and look for the
`assumed_state` attribute.

**No dongle means no commands.** `_handle_device_command` returns early with
"serial not connected", so a click in HA sends nothing and the state echo does
not run. Exercise that logic directly instead:

```bash
docker exec -i <dc> docker exec -i -w /app app_local_enocean-mqtt-ui-beta python3 - <<'PY'
import asyncio, main
class FakeMQTT:
    def get_last_state(self, n): return {"rssi": -70}
    async def publish_state(self, n, s): print(n, s)
main.mqtt_handler = FakeMQTT()
asyncio.run(main._echo_switch_state("Dev", "ON"))
PY
```

The same trick decodes synthetic telegrams against the real EEP profiles
(instantiate `EEPManager("/data")`, `await initialize()`, then
`object.__new__(SerialHandler)` with `eep_manager` set and call
`_decode_telegram`). That is how the Eltako BO/BI convention was settled.

**Entity ids never change.** Home Assistant assigns an entity id once. After a
naming fix the friendly name updates but the id keeps its old shape. Judge
naming by `friendly_name`, not `entity_id`.

## Environment traps

These cost real time when hit cold. `up.sh` handles all of them.

- **After a host reboot the inner dockerd will not start.** A stale containerd
  survives; dockerd dies with "timeout waiting for containerd to start" while
  logging that containerd is still running. Kill both, drop the sockets.
- **`supervisor_run` looks hung for up to 20 minutes.** It is in
  `docker system prune -f`, and vfs deletes layers very slowly. It buffers all
  output until exit. Check `ps` for the prune before assuming it died.
- **Add-on installs are blocked as unhealthy** (`docker_gateway_unprotected`).
  Supervisor applies gateway iptables rules through a systemd transient unit
  that cannot work here. Apply the rules manually and patch
  `host/firewall.py` to stop failing the check. Both are lost every time
  `supervisor_run` recreates the supervisor container.
- **The Supervisor integration in HA goes to `setup_retry` with 403.** The
  core container holds the token it was created with, which a restarted
  supervisor rejects. Recreate the core container, do not restart it.
- **Rebuild fails with "not available inside store".** The supervisor cannot
  see the repo: bind mounts are rprivate, so a mount made after the supervisor
  container started is invisible to it. Mount first, then restart the
  supervisor. **A failed rebuild can leave the add-on uninstalled and delete
  its `/data`,** taking all configured devices with it. `rebuild.sh` refuses to
  run in that state. Back up the add-on config from its Settings page first.

## Restoring test data

The add-on's Settings page can export and restore its config. A restore brings
the devices back but not their states, so follow it with `seed-states.sh`.
