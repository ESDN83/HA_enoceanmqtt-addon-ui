#!/bin/bash
# Build the add-on image from the repo, the way the store does it. Run this
# before releasing, so the shipped artifact is proven, not just the files that
# deploy.sh copied into a running container.
set -u
cd "$(dirname "$0")" && . ./lib.sh

# The supervisor reads local apps from its own mount of /mnt/supervisor. A bind
# mount created after that container started is not visible to it (docker bind
# mounts are rprivate), and rebuild then fails with "not available inside
# store". A failed rebuild can leave the add-on uninstalled and delete its
# /data, so check first.
if ! dcd exec hassio_supervisor test -f /data/apps/local/HA_enoceanmqtt-addon-ui/addon-beta/config.yaml 2>/dev/null; then
  echo "The supervisor cannot see the repo, so a rebuild would fail and may"
  echo "uninstall the add-on (losing /data with your devices)."
  echo "Fix: make sure $STORE_SRC is bind mounted, then restart the supervisor:"
  echo "  docker exec $DC mount --bind /workspaces/HA_enoceanmqtt-addon-ui $STORE_SRC"
  echo "  docker exec $DC docker restart hassio_supervisor"
  echo "and re-apply the firewall patch (up.sh step 6). Back up the add-on"
  echo "config from its Settings page first."
  exit 1
fi

log "reloading store"
cli store reload >/dev/null 2>&1
cli addons info "$ADDON_SLUG" --raw-json | python3 -c "
import sys,json; d=json.load(sys.stdin)['data']
print(f\"  installed={d.get('version')} store={d.get('version_latest')}\")" 2>/dev/null

log "rebuilding (minutes on vfs)"
cli addons rebuild "$ADDON_SLUG" 2>&1 | grep -v deprecated | tail -2

wait_for "add-on" 600 addon_up || true
exec ./status.sh
