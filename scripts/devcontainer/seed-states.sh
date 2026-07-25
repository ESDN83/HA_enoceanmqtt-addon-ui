#!/bin/bash
# Give every device a state so nothing sits at "unknown".
#
# Without a dongle no telegram ever arrives, entities stay unknown, and Home
# Assistant draws two on/off buttons instead of a toggle. That is a rendering
# rule, not a bug, but it is indistinguishable from the assumed_state problem
# by eye. Seed first, then judge.
#
# The add-on republishes /data/last_states.yaml on startup, so this writes that
# file and restarts. Values are derived per role from the device list, so it
# also works after restoring a config backup.
set -u
cd "$(dirname "$0")" && . ./lib.sh

addon_api /api/devices > /tmp/_devs.json 2>/dev/null || die "add-on API not reachable"

python3 - /tmp/_devs.json > /tmp/_states.yaml <<'PY'
import json, sys
devs = json.load(open(sys.argv[1]))
ts = "2026-07-25T10:00:00+00:00"
out = []
for i, d in enumerate(devs):
    role, eep = d.get("actuator_type"), f"{d['rorg']}-{d['func']}-{d['type']}"
    lines = [f"{d['name']}:"]
    if role == "light":
        lines += ['  state: "ON"', "  brightness: 60"]
    elif role == "switch":
        lines += [f'  state: "{"ON" if d.get("channel") else "OFF"}"']
    elif role == "cover":
        lines += ['  state: "open"'] + (["  POS: 30"] if eep.startswith("D2-05") else [])
    elif eep.startswith("A5-02"):
        lines += ["  TMP: 21.5"]
    elif eep.startswith("F6-02"):
        # The Rocker A/B sensors read R1_text / R2_text, not R1.
        lines += ["  R1: 0", '  R1_text: "AI"', "  R2: 0", '  R2_text: "AI"', "  EB: 0", "  SA: 0"]
    lines += [f"  rssi: -{55 + i}", f'  last_seen: "{ts}"']
    out.append("\n".join(lines))
print("\n".join(out))
PY

# Two hops: the file is on the host, but docker cp runs inside the devcontainer.
docker cp /tmp/_states.yaml "$DC:/tmp/_states.yaml" >/dev/null
dcd cp /tmp/_states.yaml "$ADDON_CT:/data/last_states.yaml"
echo "  seeded $(grep -c '^[A-Za-z_]' /tmp/_states.yaml) devices"
dcd restart "$ADDON_CT" >/dev/null 2>&1
wait_for "add-on" 180 addon_up
dcd logs --tail 30 "$ADDON_CT" 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -iE "Republished|Published HA discovery" | tail -2
