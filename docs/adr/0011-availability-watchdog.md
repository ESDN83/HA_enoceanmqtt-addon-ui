# 0011. Availability is opt-in per device, and measured from last contact

Status: accepted (1.8.0-beta5), reference rule revised in 1.8.0-beta6 after field
data. Implements issue #37.

## Context

Per-device availability existed but nothing drove it. `publish_device_availability`
was called in exactly two places: once per device at startup, and once when a
device was created. Never again. A sensor whose battery died three weeks ago
still read `online`; in Home Assistant it was indistinguishable from a healthy
one, it simply stopped changing.

Two things made a naive fix wrong.

**The state cache works against liveness.** With `cache_device_states` on,
`republish_cached_states()` writes the last known value as a retained message on
every start, and startup then marks every device `online`. A flat battery
therefore looks freshly reported after each restart. The cache preserves the
value, which is its job, but it also preserves the impression of life, and those
are two different claims.

**Not every device is supposed to talk.** A switch actuator transmits only when
it is switched. A watchdog applied to everything would declare healthy hardware
dead during any quiet evening. The reporting interval also varies by orders of
magnitude: the tester's Kessel Staufix is normally silent for at least eight
hours, while a temperature sensor reports every few minutes. One global timeout
cannot serve both.

Separately, the gateway's own Last Will sat on `enoceanmqtt/__system/status` and
no entity referenced it. On a graceful stop the shutdown path writes `offline`
per device, but a crash never reaches that code, and a crash is exactly when it
matters. Every entity kept reading `online` while nothing was listening to the
radio.

## Decision

**Opt-in per device.** `availability_timeout` is a number of minutes on the
device; `0` means never and is the default, so no existing installation changes
behaviour on update. The UI shows a checkbox and reveals the interval only when
it is ticked.

**The option is offered for actuators too, not hidden.** A D2-01 module reports
unsolicited on every physical toggle, so watching one is legitimate. Defaulting
to off is enough protection; removing the choice would take a real case away.

**The deadline runs from the device's `last_seen`, which survives a restart in
the state cache.** Boot is the reference only for a device nothing has ever been
heard from, which has no timestamp to judge; that one gets one full interval to
introduce itself.

beta5 shipped a different rule, the later of `last_seen` and the add-on's start,
on the argument that an add-on outage would otherwise punish every device for
timestamps that went stale through no fault of their own. Field data on #37
disproved it. An A5-30-03 that had been silent for 47 hours was reported
unavailable exactly one interval after a restart, so every restart cleared a
genuinely dead device and cost up to a full interval of detection time. The
add-on being down does not shorten a device's own reporting interval, so booting
is no reason to grant an extra one. A device that is in fact alive corrects the
verdict with its next telegram, which is what `unavailable` is supposed to mean.

What boot does need is a **settling window**: MQTT has to connect and the cached
states have to be republished before any verdict is based on real data.
`AVAILABILITY_STARTUP_GRACE_SECONDS` is two minutes, a one-off pause, not a
second interval.

**Availability is published only when it changes**, so the retained topic is not
rewritten every minute. Switching the watchdog off republishes `online` once, so
a device cannot stay stuck unavailable.

**The gateway LWT becomes a second availability entry** on every discovery
config, with `availability_mode: all`. It is applied in one place at the end of
`get_ha_discovery_configs` rather than at each of the eight config sites, so no
entity can be missed. This is independent of the watchdog and covers every
device, opted in or not.

## Consequences

A device coming back is noticed within one check interval (60 seconds) rather
than instantly, because the watchdog polls rather than hooking the telegram
path. For an eight-hour reporting interval that is irrelevant, and it keeps the
change out of the receive path.

`unavailable` here means "the add-on has heard nothing in time", not "the device
is broken". That is the honest claim, and it matches what the Home Assistant
state is for.

Users must pick an interval, and a value that is too tight produces false
alarms during normal quiet periods. The field hint says so explicitly. Deriving
a suggestion from the observed gaps between telegrams is the obvious next step
and is deliberately not in this change.
