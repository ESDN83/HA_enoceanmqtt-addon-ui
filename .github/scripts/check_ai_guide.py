"""Fail when the AI assistant guide names an endpoint the app does not have.

Assistants act on the guide (ADR-0033), so a stale path sends them into
errors. Each `/api/...` path in ai_guide.md must match a route: the router
prefix from main.py plus a route path from api/*.py, `{param}` matching any
segment.
"""
import glob
import os
import re
import sys

failed = False
for app in sorted(glob.glob("addon*/rootfs/app")):
    main = open(os.path.join(app, "main.py"), encoding="utf-8").read()
    if "/api/ai/guide" not in main:
        continue
    guide_file = os.path.join(app, "data", "ai_guide.md")
    if not os.path.exists(guide_file):
        print(f"{app}: main.py serves /api/ai/guide but {guide_file} is missing")
        failed = True
        continue
    routes = set(re.findall(r'@app\.(?:get|post|put|delete)\("([^"]+)"', main))
    for module, prefix in re.findall(r'include_router\((\w+)\.router, prefix="([^"]+)"', main):
        src = open(os.path.join(app, "api", f"{module}.py"), encoding="utf-8").read()
        for path in re.findall(r'@router\.(?:get|post|put|delete|websocket)\("([^"]*)"', src):
            routes.add(prefix + path)
    patterns = [re.compile("^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(r).replace(r"\:path", "")) + "$")
                for r in routes]
    guide = open(guide_file, encoding="utf-8").read()
    for path in sorted(set(re.findall(r"`(?:GET |POST |PUT |DELETE )?(/(?:api/[^`?\s]*|openapi\.json|health))", guide))):
        path = path.rstrip("/")
        if not any(p.match(path) for p in patterns) and path != "/openapi.json":
            print(f"{guide_file}: {path} is not a route of the app")
            failed = True
    print(f"{guide_file}: checked")
sys.exit(1 if failed else 0)
