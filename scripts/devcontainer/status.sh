#!/bin/bash
# One-shot health check of the devcontainer test stack.
set -u
cd "$(dirname "$0")" && . ./lib.sh

[ -n "$DC" ] && echo "devcontainer : $DC ($(docker inspect -f '{{.State.Status}}' "$DC" 2>/dev/null))" \
             || { echo "devcontainer : not found"; exit 1; }

echo -n "inner docker : "; dcd info --format 'ok, {{.ServerVersion}} driver={{.Driver}}' 2>/dev/null || echo "DOWN"
echo -n "supervisor   : "
cli resolution info --raw-json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('healthy' if not d['unhealthy'] else 'UNHEALTHY '+str(d['unhealthy']))" 2>/dev/null || echo "no API"

echo -n "add-on       : "
cli addons info "$ADDON_SLUG" --raw-json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print(f\"{d.get('state')} installed={d.get('version')} store={d.get('version_latest')}\")" 2>/dev/null || echo "not installed"

echo -n "store source : "
dcd exec hassio_supervisor test -f /data/apps/local/HA_enoceanmqtt-addon-ui/addon-beta/config.yaml 2>/dev/null \
  && echo "visible (rebuild works)" || echo "MISSING, supervisor cannot rebuild (bind mount lost, see up.sh step 4)"

echo -n "devices      : "
addon_api /api/devices 2>/dev/null | python3 -c "
import sys,json; ds=json.load(sys.stdin); print(f'{len(ds)}:', ', '.join(d['name'] for d in ds) or 'none')" 2>/dev/null || echo "add-on API not reachable"

echo -n "HA core      : "
curl -s -o /dev/null -m 3 -w "reachable (http://%{remote_ip}:7123)\n" http://localhost:7123 2>/dev/null || echo "not reachable on :7123"
