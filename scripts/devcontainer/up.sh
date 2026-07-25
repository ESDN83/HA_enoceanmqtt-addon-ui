#!/bin/bash
# Bring the devcontainer HA test stack up from a cold host (after a reboot).
# Idempotent: safe to re-run. Takes 2 to 25 minutes, the spread is the
# docker prune inside supervisor_run (vfs deletes layers very slowly).
set -u
cd "$(dirname "$0")" && . ./lib.sh

[ -n "$DC" ] || die "no devcontainer found. Run: devcontainer up --workspace-folder ."

log "1/7 start devcontainer $DC"
docker start "$DC" >/dev/null 2>&1
sleep 5
dc mkdir -p /run/supervisor
dc mount --make-rshared / 2>/dev/null   # core needs /mnt/supervisor/media shared

log "2/7 clear stale docker state"
# A stale containerd from before the reboot makes dockerd die with
# "timeout waiting for containerd to start" while it logs that containerd
# is still running. Kill both and drop the sockets.
dc sh -c 'pkill -9 containerd 2>/dev/null; pkill -9 dockerd 2>/dev/null; sleep 2;
          rm -f /var/run/docker.pid /run/containerd/containerd.sock /var/run/docker.sock' 2>/dev/null

log "3/7 start inner dockerd"
docker exec -d "$DC" sh -c 'nohup dockerd --storage-driver=vfs >/var/log/dockerd.log 2>&1 &'
wait_for "inner docker" 180 dcd info || die "dockerd did not come up, see /var/log/dockerd.log in $DC"

log "4/7 mount the repo where the supervisor store reads local apps"
# Docker bind mounts are rprivate, so this must exist before the supervisor
# container starts or the store shows the add-on as "not available inside
# store" and rebuild fails.
dc sh -c "mountpoint -q $STORE_SRC || mount --bind /workspaces/HA_enoceanmqtt-addon-ui $STORE_SRC"

log "5/7 supervisor_run (slow: docker system prune on vfs, no output while it runs)"
docker exec -d "$DC" sh -c 'nohup script -qec supervisor_run /dev/null >/var/log/supervisor_run.log 2>&1 &'
wait_for "supervisor" 2000 sh -c "docker exec $DC docker ps --format '{{.Names}}' | grep -q hassio_supervisor"
wait_for "supervisor API" 600 supervisor_ok

log "6/7 gateway firewall workaround"
# Supervisor applies its gateway iptables rules through a systemd transient
# unit. systemd is not reachable here, so it marks the system unhealthy and
# blocks every add-on install. Apply the rules by hand, then stop the check
# from failing. Both are lost whenever supervisor_run recreates the container.
dc sh -c '
GW4=172.30.32.1; GW6=fd0c:ac1e:2100::1; BR=hassio
iptables  -t raw -C PREROUTING ! -i $BR -d $GW4 -j DROP  2>/dev/null || iptables  -t raw -I PREROUTING ! -i $BR -d $GW4 -j DROP
iptables  -t raw -C PREROUTING -i lo   -d $GW4 -j ACCEPT 2>/dev/null || iptables  -t raw -I PREROUTING -i lo   -d $GW4 -j ACCEPT
ip6tables -t raw -C PREROUTING ! -i $BR -d $GW6 -j DROP  2>/dev/null || ip6tables -t raw -I PREROUTING ! -i $BR -d $GW6 -j DROP
ip6tables -t raw -C PREROUTING -i lo   -d $GW6 -j ACCEPT 2>/dev/null || ip6tables -t raw -I PREROUTING -i lo   -d $GW6 -j ACCEPT' >/dev/null 2>&1
docker exec -i "$DC" docker exec -i hassio_supervisor python3 - <<'PY'
p = "/usr/src/supervisor/supervisor/host/firewall.py"
s = open(p).read()
old = '''        if not self.sys_dbus.systemd.is_connected:
            _LOGGER.error("Systemd not available, cannot apply gateway firewall rules")
            return False'''
new = '''        if not self.sys_dbus.systemd.is_connected:
            _LOGGER.warning("Systemd not available; gateway firewall rules applied manually (devcontainer test patch)")
            return True'''
if old in s:
    open(p, "w").write(s.replace(old, new, 1)); print("  firewall patched")
elif new in s:
    print("  firewall already patched")
else:
    print("  WARNING: firewall patch anchor not found, supervisor may stay unhealthy")
PY
dcd restart hassio_supervisor >/dev/null 2>&1
wait_for "supervisor API" 300 supervisor_ok
cli resolution info --raw-json | python3 -c "import sys,json;print('  unhealthy:',json.load(sys.stdin)['data']['unhealthy'])" 2>/dev/null

log "7/7 core and add-ons"
# The core container keeps the supervisor token it was created with. After a
# supervisor restart that token is rejected (403 on /addons, hassio integration
# stuck in setup_retry), so recreate the container rather than restart it.
cli core stop >/dev/null 2>&1
dcd rm -f homeassistant >/dev/null 2>&1
cli core start >/dev/null 2>&1
dcd rm -f "$ADDON_CT" app_core_mosquitto >/dev/null 2>&1
cli addons start core_mosquitto >/dev/null 2>&1
sleep 15
cli addons start "$ADDON_SLUG" >/dev/null 2>&1
wait_for "add-on" 300 addon_up

log "done"
exec ./status.sh
