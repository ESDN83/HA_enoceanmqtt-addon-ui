# 0009. The device name is a key, a topic and a URL segment at once

Status: accepted (v1.7.2). Prompted by issue #36.

## Context

A device name is used for three different jobs:

1. the primary key of `devices.yaml` and of the in-memory device map,
2. the base of its MQTT topics (`enoceanmqtt/<name>/state|set|availability`),
3. a path segment in the web UI's API calls (`/api/devices/<name>`),

and, before this change, a fourth by accident: it was interpolated into the
`onclick` attributes of the Edit and Delete buttons.

Renaming a device shipped in 1.7.0. That turned a name from something the
wizard mostly generated into free user text, and the assumptions above stopped
holding. A tester renamed a module to a name containing an apostrophe. The
generated markup was `onclick="deleteDevice('Volet d'entrée')"`, the apostrophe
ended the JavaScript string, and both buttons became dead. The card's own
click handler broke the same way, so the device could not be opened either.
There was no route left in the UI to reach it. Delete also never checked the
response, so on the paths that produced a 404 instead (`/` and `#` in a name)
the UI reported "Device deleted" while the device stayed.

A separate failure sat behind the same key. `last_states.yaml` is keyed by
device name, and `republish_cached_states()` writes a retained state message
for every name it holds on every start. Delete and rename never touched it, so
a removed name kept getting a retained state republished at each restart, and a
device later given that name inherited a stranger's state.

## Decision

Keep the name as the key. Changing that means migrating `devices.yaml`, every
MQTT topic and every existing HA entity, which is not worth it for a field
that users want to read in the topic anyway. Instead, make each of the three
jobs handle arbitrary text correctly, and reject only what genuinely cannot
work:

- **Markup.** A name never goes into an attribute. The device cards and the
  detail view are built without inline handlers, and listeners take the name
  from the closure. Every displayed field goes through `escapeHtml`.
- **URLs.** Every API call that carries a name uses `encodeURIComponent`.
- **Responses.** `deleteDevice`, `editDevice` and `showDeviceDetail` check
  `response.ok` and surface the server's `detail`.
- **Validation.** `/`, `+` and `#` are rejected server-side on create and
  rename. They are illegal or ambiguous in an MQTT topic segment, so no amount
  of encoding makes them usable. Quotes and accented characters are allowed.
- **Ownership of the name's leftovers.** Delete and rename clear the retained
  `state` and `availability` topics and the state-cache entry for the old
  name. A rename carries the cached state over first. A startup prune drops
  cache entries whose name is no longer in `devices.yaml`, which cleans up
  what earlier versions left behind.

## Consequences

Any name a user can type works, including apostrophes and accents, which
matters because the testers are French and German speakers.

Validation is deliberately narrow. Rejecting more (spaces, dots, non-ASCII)
would break existing installations, since those names are already in use and
in topics.

The startup prune only touches names this add-on itself wrote into its own
cache file. It never enumerates or deletes foreign topics on the broker, so a
shared broker is not at risk.

Retained messages under names removed *before* 1.7.2 are cleared by the prune
on the first start after updating, because the name is still in the state cache
even though the device is gone. A name that was never in the cache (a device
deleted before it ever reported) leaves nothing behind to clear.

## Follow-up: names that already contain a slash (v1.7.3, 1.8.0-beta6)

Validation stops a new slash, but it does nothing for the devices that already
have one, and 1.7.2 left those completely stranded. The reporter of #36 came
back with `Boulodrome/Chemin` and two more like it: still impossible to delete,
now with the message "Not Found".

The cause is in the routing, not in the handler. The server decodes the URL
before matching a route, so `encodeURIComponent`'s `%2F` arrives as a real `/`,
`/api/devices/Boulodrome/Chemin` matches no route at all, and FastAPI answers
with its own 404 `{"detail": "Not Found"}`. GET, PUT and DELETE were all
unreachable, so the device could not even be opened, let alone renamed out of
the problem. Verified against a running instance: `/api/devices/a%2Fb` returns
`{"detail": "Not Found"}` while `/api/devices/zzz` reaches the handler and
returns `{"detail": "Device 'zzz' not found"}`.

The three routes take `{name:path}`. The `search` route is declared before them
and still wins, since routes match in declaration order. Validation is
unchanged, so this creates no new slash names; it only makes the existing ones
reachable long enough to be renamed.

Renaming them is not optional, because the slash breaks a second thing that no
routing change can fix: commands are subscribed as `{prefix}/+/set`, and a
single-level wildcard does not match `enoceanmqtt/Boulodrome/Chemin/set`. An
actuator with a slash in its name receives nothing from Home Assistant.
