# 0009. Loading the split frontend without a build step

Status: accepted (1.8.0-beta1).

## Context

`templates/index.html` was split from 4128 lines into a stylesheet and ten JavaScript files (ADR-0006 and `docs/FRONTEND_REFACTOR_PLAN.md`). The files still have to reach the browser, and three constraints collide:

- There is no bundler and none is wanted, so every file is a plain `<link>` or `<script src>`.
- Under Home Assistant Ingress the base path is dynamic (`/api/hassio_ingress/<token>/`), so no href can be written statically into the template.
- The 59 inline `onclick` handlers call bare function names, so the files must be classic scripts that run before the handlers can fire, in dependency order.

The obvious approach, building the elements with `createElement` and appending them to `<head>`, was tried first and measured.

## Decision

Emit the `<link>` and the `<script src>` tags with `document.write`, from a small inline script in `<head>`, with the base path computed from `window.location` exactly as `getApiUrl()` and the existing js-yaml loader already do.

`app.js`, which holds the wiring, is written by a second such snippet at the **end of `<body>`**, not in `<head>` with the other nine.

## Consequences

- **`document.write` is deliberate, not legacy.** A `<link>` inserted from script is classified `renderBlockingStatus: "non-blocking"`, measured in the browser: the page may paint before the stylesheet arrives, which is a flash of unstyled content on a cold load. Written into the parser during the initial parse of `<head>` the same element measures `"blocking"`. The rule that makes `document.write` harmful, calling it after load, does not apply here.
- Parser-inserted scripts execute in document order, which gives the load order the split needs for free: shared helpers first, feature files after. Adding a file is one more entry in the array.
- `app.js` calls `detectAndApplyTheme()` immediately at the point it loads. The inline block it replaced sat at the end of the body, so loading it in `<head>` would apply the theme earlier than before. Keeping its position keeps the timing, which is what makes the split a move rather than a change. See ADR-0002 for why theme timing is delicate here.
- Functions stay global. No ES modules in this pass: module scope would break every inline handler.
- The cost is one small piece of inline JavaScript that cannot itself be moved into a file, since it is what loads the files.
