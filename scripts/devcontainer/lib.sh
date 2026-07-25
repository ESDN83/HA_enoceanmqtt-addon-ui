#!/bin/bash
# Shared helpers for the devcontainer test scripts.
# Source this, do not run it directly.

ADDON_SLUG="${ADDON_SLUG:-local_enocean-mqtt-ui-beta}"
ADDON_CT="app_${ADDON_SLUG}"
APP_SRC="/workspaces/HA_enoceanmqtt-addon-ui/addon-beta/rootfs/app"
STORE_SRC="/mnt/supervisor/apps/local/HA_enoceanmqtt-addon-ui"

log() { echo "[$(date +%H:%M:%S)] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

# The devcontainer gets a random name, so find it by image.
find_dc() {
  docker ps -a --filter "ancestor=ghcr.io/home-assistant/devcontainer:addons" \
    --format '{{.Names}}' | head -1
}
DC="${DC:-$(find_dc)}"

# Run inside the devcontainer / inside its nested docker.
dc()   { docker exec "$DC" "$@"; }
dcd()  { docker exec "$DC" docker "$@"; }
cli()  { docker exec "$DC" docker exec hassio_cli ha "$@" 2>/dev/null; }
addon(){ docker exec "$DC" docker exec "$ADDON_CT" "$@"; }

# Wait for a command to succeed, with a timeout in seconds.
wait_for() {
  local what="$1" timeout="$2"; shift 2
  local waited=0
  while ! "$@" >/dev/null 2>&1; do
    sleep 3; waited=$((waited + 3))
    [ "$waited" -ge "$timeout" ] && { echo "  timeout waiting for $what after ${timeout}s"; return 1; }
  done
  echo "  $what ready after ${waited}s"
}

addon_up()      { dcd logs --tail 5 "$ADDON_CT" 2>&1 | grep -q "Web UI running on port 8099"; }
supervisor_ok() { cli resolution info --raw-json | grep -q '"result":"ok"'; }
addon_api()     { addon curl -sf "localhost:8099$1" "${@:2}"; }
