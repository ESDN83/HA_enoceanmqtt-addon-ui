# ADR-0012: Serialized transmit path and an inbound command queue

Date: 2026-08-08
Status: Accepted (beta, 1.8.0-beta7; queue observability added in 1.8.0-beta8)
Issue: #38

## Context

A user reported that switching several Eltako F4SR14 relays in a row left some
of them physically unswitched, while Home Assistant showed all of them in the
commanded state. Debug logs from the field (14 devices per script run, USB300
dongle) pinned it down:

- Commands spaced ~300 ms apart all worked, every time.
- Below roughly 300 ms it became unreliable.
- Each command occupied the add-on for ~105 ms: press telegram, dongle
  acknowledgement, 100 ms hold, release telegram.

Three defects were behind it.

**Commands ran concurrently.** `mqtt_handler._handle_command` dispatched every
inbound MQTT message with `asyncio.run_coroutine_threadsafe` and never awaited
the result. A scene therefore started N handlers at once, and their telegrams
were written into the transceiver back to back. The module has one radio and a
small transmit queue: what does not fit is rejected or dropped.

**Nobody looked at the answer.** The transceiver acknowledges every radio
packet with a RESPONSE carrying a return code, and reports a full queue as
RET_NOT_OK. The read loop logged that packet at debug level and discarded it.
`send_telegram` returned True regardless.

**The state echo was unconditional.** Because the send always claimed success,
the optimistic echo went out even for a telegram that never reached the air.
That is why Home Assistant looked right while the relay stayed on, and why
nothing in the log said otherwise.

The reporter's own hypothesis, that commands were lost on the MQTT subscriber
side, does not hold: `MQTT RX` is logged as the first statement of the paho
callback before any await, so a busy event loop cannot suppress it, and paho
does not silently discard inbound QoS 1 messages. Both log excerpts were
truncated at the front, which is why the first five commands appeared to be
missing.

## Decision

Serialize the transmit path, queue inbound commands, and never echo a state
for a telegram the transceiver did not take.

**One request in flight.** All traffic to the module, radio telegrams and ESP3
common commands alike, goes through `SerialHandler._tx_slot()`. Response
packets carry no sequence number, so two outstanding requests could hand a
radio acknowledgement to whoever asked for a base ID. Consecutive writes keep
a 40 ms gap.

**The press/release pair is atomic.** An Eltako actuator reads the press
duration as part of the command: a short press runs a shutter its full travel,
a long one moves it only while held. If pacing stretched a 100 ms hold to 600
ms, a close command would become a nudge. `send_rps_press_release` therefore
holds the transmit slot across press, hold and release, so no other telegram
can get between them. The hold is measured write to write and logged as a
warning above 250 ms.

**The release always goes out.** It is sent from a `finally` block, and the
whole pair is wrapped in `asyncio.shield`. A command deadline or a shutdown
must never abandon a press: an unterminated press leaves an Eltako shutter
running until its own travel time expires.

**Inbound commands go through `core/command_queue.py`.** A bounded queue feeds
two workers. A per-device lock keeps two commands for the same device in
order. Every command has a 2 s deadline, after which it is abandoned and the
queue continues, so one stuck command cannot park the send path. Queue
overflow and backlog are logged; `/health` exposes pending, dropped and
timed-out counters.

**Send results gate the echo.** `send_telegram` returns True only on an
acknowledged telegram, and every caller in `_handle_device_command` skips the
state echo and logs a warning when it is False.

## Consequences

Sustained throughput is now bounded by the radio, not by chance: roughly nine
commands per second, so a 14 device scene takes about 1.5 s. That is slower
than firing everything at once but it is the rate the hardware actually
sustains, and the previous behaviour bought its speed by dropping telegrams.

There is no parallelism at the radio layer and this ADR does not pretend
otherwise. A configurable RF retry, which the reporter suggested, was
rejected: whether repeating a press is idempotent depends on how the actuator
was taught. On a toggle-taught relay a repeat switches it back off.

One residual risk remains. The hold is protected against other telegrams but
not against event-loop starvation: a long synchronous stretch elsewhere in the
add-on can still delay a release. That is what the 250 ms warning is for.

## Follow-up in 1.8.0-beta8: the queue is observable

Field feedback confirmed beta7: 43 telegrams in a nine-cover plus fourteen-light
burst, 43 acknowledgements, all RET_OK, nothing lost, no delays needed in the
reporter's scripts any more. Two things came out of it.

**Nothing tells Home Assistant when the radio has caught up.** A script returns
once its MQTT commands are published. With the queue behind it, the last
command of a 23 command burst reached the air 2.8 s later. Chaining two scripts
therefore still meant guessing a delay, for anyone whose next step depends on
the physical result. The queue now tracks in-flight commands next to pending
ones and publishes `{prefix}/__system/queue`, exposed as three diagnostic
entities on a gateway device: busy, pending, and the duration of the last busy
period. They are `enabled_by_default: False`, because the majority never needs
them and beta7 already removed the reason to wait at all. Busy transitions are
published immediately (that is the edge an automation waits on), the pending
count in between is throttled to twice a second.

Idle means pending zero **and** nothing in flight. An empty queue with a
telegram still on the air is not idle, and an automation keying off that would
act too early.

The gate is an add-on option (`gateway_diagnostics`, off by default), not
`enabled_by_default: False` on the entities. Two reasons. The option is the one
place a user reads a description explaining when this is needed, and one
decision should not have to be made twice: after ticking the box the entities
arrive switched on rather than needing a second visit to each one. Switching
the option off **removes** the discovery configs. That is not optional
politeness: a retained discovery config outlives the add-on that published it,
so without an active removal the entities would sit in Home Assistant as
unavailable forever.

The `unique_id` values (`enocean_gateway_*`) are a compatibility contract.
Home Assistant keys its entity registry on them, which is what makes user
renames, area assignment, icon overrides and per-entity disabling survive every
rediscovery. Renaming a `unique_id` in a later version would orphan the old
entity and silently break any automation referring to it, so they do not
change. The published documentation names entity ids only as the shipped
default, and says to substitute your own after a rename.

**beta7 broke the per-telegram log line.** `TX EnOcean` was written in
`send_telegram` but not in the pair path, so 40 of those 43 telegrams left no
trace and the field log could only be read by counting response packets. The
line moved into `_send_radio_packet`, which every telegram goes through. The
cover path also never said whether a command went out, and covers carry no
state echo, so that log line is the only evidence there is.

Verified against a fake ESP3 transport: a 14 command burst with zero spacing
keeps its order, produces 28 telegrams with a minimum gap of 41 ms and holds
of 101 to 152 ms, emits no warnings, survives cancellation mid-hold with the
release still sent, fails fast on a stalled write while draining the queue,
and reports RET_NOT_OK as a failure. Field verification on the reporter's
installation is still open.
