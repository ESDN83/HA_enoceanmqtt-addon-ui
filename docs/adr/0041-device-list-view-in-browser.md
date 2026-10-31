# 0041. Device list sort and view are kept in the browser

Status: proposed (v1.8.5-beta20).

## Context

Issue #54 and the maintainer asked for a sorted device list (name, last
seen, status, room) and a list view next to the cards, kept across
restarts. The stored device order is insertion order, so a renamed device
moves to the end.

## Decision

- Sorting, grouping and the view are display only. The stored order, MQTT
  topics and discovery are untouched.
- `GET /api/devices?include=state` adds read-only `_last_seen`, `_state`
  and `_available` per device. Without the parameter the response is
  unchanged, so other readers (the device edit form, scripts) see no
  difference.
- The choice is kept in the browser's localStorage, guarded: without
  storage the defaults (name A-Z, cards) apply. It is a viewing preference,
  and keeping it per browser lets a phone use the list and a desktop the
  cards. It survives app restarts and updates.
- Status sorts offline devices first (the availability watchdog's
  verdict), then devices never heard from, then the rest, by name within
  each.

## Consequences

- A preference does not follow the user to another browser.
