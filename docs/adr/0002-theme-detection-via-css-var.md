# 0002. Theme detection reads HA's background CSS variable

Status: accepted (v1.7.0-beta6), after a wrong first fix (beta4).

## Context

The web UI runs in an Ingress iframe and mirrors HA's light/dark theme. Detecting the theme by reading the parent body background (`getComputedStyle(parent.body).backgroundColor`) failed: Home Assistant's `<body>` usually has no background of its own, so it computes to `rgba(0,0,0,0)` (transparent). A brightness parser read that as pitch black and concluded HA was dark. A light HA was then rendered dark, and every surface styled by Bootstrap's `data-bs-theme` or `color-scheme` (the mapping editor `bg-body-tertiary`, tables, `<code>` badges, native number spinners) went dark on the light page.

An intermediate fix (beta4) let the OS `prefers-color-scheme` override a detected light HA, which produced the same mixed result.

## Decision

Both detection paths (the early anti-flash `<head>` script and `detectAndApplyTheme`) read HA's own `--primary-background-color` CSS variable, which is the color HA actually paints and the same source the app inherits its colors from. A transparent result is treated as "unknown" and ignored. The OS preference applies only when the app runs standalone (cross-origin, no readable parent). `applyHAThemeVars` also drives `--input-bg`, `--input-border`, and `--code-bg` from HA variables so fields and badges cannot disagree with the page.

## Consequences

- Theme attributes and inherited colors are consistent by construction.
- The anti-flash `<head>` script must stay inline; do not externalize it.
- When testing theme changes, the harness parent must have a transparent body to be representative. See `docs/testing.md`.
