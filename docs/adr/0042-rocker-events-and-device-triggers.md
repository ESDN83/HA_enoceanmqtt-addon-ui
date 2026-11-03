# 0042. Rocker presses are events on their own topic

Status: proposed (v1.8.6-beta1).

## Context

Issue #56. A rocker (F6-02-01/02) was exposed as Rocker A/B text sensors
and momentary Button AI..BO binary sensors. An automation had to watch a
binary sensor flip ON and OFF. Home Assistant models buttons as events
(`event` entity) and device triggers, and other EnOcean integrations offer
both.

## Decision

- Every press and release is published to `{prefix}/{device}/event`, not
  retained, payload `{"event_type": "<button>_<action>", "button", "action"}`.
  The state topic is retained and republished at start, so a trigger on it
  would fire for an old press.
- Actions: `press`, `release` (before 0.6 s), `long_press` (still held at
  0.6 s, fires while held), `long_release`. Device trigger types
  `button_short_press`, `button_short_release`, `button_long_press`,
  `button_long_release`, subtype `Button <AI|AO|BI|BO>`.
- One `event` entity per rocker with all 16 event types, plus 16 device
  triggers. Unique IDs follow the usual `enocean_<eep>_<addr>_...` format,
  so ADR-0026 cleanup covers them.
- A release (EB = 0) names no button; the buttons of the last press are kept
  per device. A press with NU = 0 (3-4 buttons) is skipped. A repeated press
  of buttons already held is ignored (repeaters).
- Only sensor-mode rockers. An actuator taught in as F6 sends confirmations.
- The existing sensors stay, so nothing breaks.

## Consequences

- 17 extra discovery configs per rocker.
- The 0.6 s threshold is fixed; a per-device setting can follow if asked.
- A lost release telegram leaves no release event; the next press closes it
  without one.
