#!/bin/bash
# Fast iteration: copy changed app files from the workspace into the running
# add-on container and restart it. Seconds instead of a full image rebuild.
#
#   ./deploy.sh                 copy every file git reports as changed
#   ./deploy.sh main.py api/devices.py    copy just those (paths under rootfs/app)
#
# The copy lives in the container filesystem: it survives a restart but not a
# rebuild or recreate. Run a real rebuild before releasing, see rebuild.sh.
set -u
cd "$(dirname "$0")" && . ./lib.sh
REPO="$(cd ../.. && pwd)"

if [ $# -gt 0 ]; then
  FILES=("$@")
else
  mapfile -t FILES < <(cd "$REPO" && git status --porcelain -- addon-beta/rootfs/app \
                        | awk '{print $NF}' | sed 's#^addon-beta/rootfs/app/##')
fi

[ ${#FILES[@]} -eq 0 ] && { echo "nothing changed under addon-beta/rootfs/app"; exit 0; }

# Syntax-check first so a typo does not take the add-on down.
for f in "${FILES[@]}"; do
  case "$f" in
    *.py)   (cd "$REPO/addon-beta/rootfs/app" && python3 -m py_compile "$f") || die "python syntax error in $f" ;;
    *.html) command -v node >/dev/null && (cd "$REPO/addon-beta/rootfs/app" && python3 - "$f" <<'PY' > /tmp/_inline.js
import re, sys
html = open(sys.argv[1], encoding="utf-8").read()
print("\n;\n".join(re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)))
PY
            node --check /tmp/_inline.js >/dev/null) || die "javascript syntax error in $f" ;;
  esac
done

for f in "${FILES[@]}"; do
  dcd cp "$APP_SRC/$f" "$ADDON_CT:/app/$f" && echo "  copied $f"
done

dcd restart "$ADDON_CT" >/dev/null 2>&1
wait_for "add-on" 180 addon_up
dcd logs --tail 30 "$ADDON_CT" 2>&1 | sed 's/\x1b\[[0-9;]*m//g' \
  | grep -iE "Loaded [0-9]+ devices|Connected to MQTT|Published HA discovery|Traceback" | tail -4
