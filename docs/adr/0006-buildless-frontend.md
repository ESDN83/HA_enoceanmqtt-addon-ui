# 0006. The frontend stays buildless

Status: accepted.

## Context

The web UI is served by FastAPI as static files with a Jinja2 template. There is no npm, bundler, or build step. Today the entire UI (HTML, CSS, JS) lives in one `templates/index.html` of around 4000 lines, which makes every change touch a huge file. The fix is to split it, but the split must not add tooling.

Two hard constraints shape any split:
- 59 inline `onclick` handlers call bare global function names. ES modules create scope and would break every handler.
- Assets load behind HA Ingress under a dynamic base path, so any new script or stylesheet must be loaded Ingress-aware.

## Decision

Keep the frontend buildless. When splitting `index.html`, extract CSS to `static/css/app.css` and JS into several classic (non-module) `.js` files loaded in dependency order, keeping functions global. Load them Ingress-aware like the existing js-yaml and i18n loaders. The anti-flash `<head>` theme script stays inline. No bundler, no framework, no ES modules in this pass.

## Consequences

- Each future UI change touches a small focused file.
- The split is pure restructuring with no behavior change, shippable one slice per beta.
- Full plan in `docs/FRONTEND_REFACTOR_PLAN.md`. Do it after v1.7.0 stable.
