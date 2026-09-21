# 0018. A failed connect leaves no socket behind, and only a usable session resets the backoff

Status: accepted (v1.8.3-beta1). Follows ADR-0017.

## Context

Two failures in the TCP reconnect path, both reported on 1.8.2 against an
ESPHome `stream_server` bridge on an ESP32 (#42).

### The reconnect loop stopped for good after one timed-out attempt

`_connect_tcp` assigned the socket to `self._socket` and *then* called
`connect()` on it. When the peer was mid-reboot the connect timed out, the
exception propagated, and a socket that had never been connected stayed in
`self._socket`.

`_serial_read` then called `recv()` on that socket. It does not raise something
the read loop would treat as a lost transport: it raises `socket.timeout`,
which `_serial_read` deliberately reports as "no data yet". The loop counted
that as idle, looped, and timed out again, forever. No exception, so no
reconnect, ever. The reporter's add-on sat like that for 22 minutes across two
peer reboots until *Restart services* was used, while an independent client
could open the same endpoint and get a valid `CO_RD_VERSION` answer.

Confirmed outside the add-on:

```
connect raised after 3.0s: TimeoutError: timed out
recv raised socket.timeout after 3.0s      <- read as idle
socket timeout still: 3.0
```

The heartbeat made it look healthy. It counted idle reads and called each one a
second, which is only true while the socket timeout is 1 s. The abandoned
socket still carried the 5 s connect timeout, so "30 s elapsed" took 150 s of
wall clock. That is exactly the spacing in the reporter's log, and it is what
made the add-on look like a quiet gateway rather than a dead one.

### The backoff never grew against a peer that accepts and hangs up

The loop reset the backoff to 1 s whenever `_wait_and_reconnect` returned True,
and a bare TCP handshake was enough for that. An ESP32 out of heap accepted
connections and sent FIN within milliseconds, so every attempt looked like a
success: roughly one attempt per second for hours, about 7000 of them in three,
which both denied the peer any chance to recover and buried every other line in
the log.

## Decision

- **A socket becomes `self._socket` only once it is connected.** It is built
  locally, connected, configured, and closed again if any of that fails. The
  next read then raises `ConnectionError: TCP socket not open`, which is a lost
  transport, which is a reconnect. A failed attempt is an attempt, never a
  reason to stop.
- **A session resets the backoff only when it proves usable**, meaning it
  carried at least one byte or lasted at least `GOOD_SESSION_SECONDS` (30 s). A
  connect on its own proves nothing. The duration rule exists because an
  EnOcean gateway is legitimately silent for minutes, so silence must not look
  like failure; an accept-then-FIN peer never comes close to it.
- **The heartbeat reports measured time**, from a monotonic clock, not a count
  of reads. And because a missing transport now raises instead of reading as
  idle, the heartbeat cannot appear while no socket exists, which is what the
  reporter asked for.
- **A retry while already disconnected logs at debug**, not as another
  "Transport lost" warning. The failed attempt is already logged by
  `_wait_and_reconnect`, and one warning per lost transport is the honest
  count.

## Consequences

- An unreachable peer now produces one reconnect attempt per backoff step up to
  30 s, indefinitely, and recovers on its own whenever the peer returns.
- After a genuinely dead session the first retry may wait up to 30 s rather
  than 1 s, because the backoff is no longer reset by the handshake. A peer
  that works is unaffected: the first byte resets it.
- `socket.timeout` meaning "idle" is safe again, because it can now only reach
  `_serial_read` from a socket that really is connected.

## Verification

The read loop was driven directly against two controllable peers, with the
shipped 1.8.2 file and the fixed one in turn, so the comparison is the same
test on both. 70 seconds per run.

**Peer unreachable (connect times out).** 1.8.2 makes exactly one attempt and
then goes quiet for the rest of the run:

```
   40ms  WARNING Transport lost: TCP socket not open, reconnecting in 1s
 6049ms  ERROR   Reconnect attempt failed: timed out
70041ms  INFO    Serial read loop stopped
```

Fixed, it keeps trying and the interval grows 2, 4, 8, 16 s:

```
 6049ms  ERROR   Reconnect attempt failed: timed out
13059ms  ERROR   Reconnect attempt failed: timed out
22065ms  ERROR   Reconnect attempt failed: timed out
35085ms  ERROR   Reconnect attempt failed: timed out
56109ms  ERROR   Reconnect attempt failed: timed out
```

No heartbeat appears in either half of that run any more, because there is no
socket to read.

**Peer accepts and sends FIN at once.** 1.8.2 makes **70** attempts in 70
seconds, one per second, which matches the reporter's ~2900 per hour. The fix
makes **6**:

```
 1352ms  Transport lost: TCP peer closed connection (FIN received), reconnecting in 2s
 3355ms  ... in 4s
 7361ms  ... in 8s
15367ms  ... in 16s
31384ms  ... in 30s
61397ms  ... in 30s
```

The first attempt at this only reset the backoff on a good session and grew it
on a failed *connect*, which against this peer never happens: the handshake
always succeeds. The session being useless has to grow it, which is the second
half of the decision above.

**On real hardware.** Finally against a production ESP bridge of the same kind
(ESPHome `stream_server` on an ESP32), with the fixed file, the transceiver
physically unplugged for two minutes:

```
203869ms  Transport lost: TCP peer closed connection (FIN received), reconnecting in 1s
206941ms  Reconnect attempt failed: [Errno 113] No route to host
211997ms  ...
219069ms  ...
230143ms  ...
249213ms  ...
282269ms  ...
315361ms  Reconnect attempt failed: [Errno 113] No route to host
345398ms  TCP connected to 192.168.1.122:8880
345398ms  Reconnected to EnOcean transceiver
345921ms  USB300 Base ID: 0xFFD1F400
```

Seven attempts over 140 s with the interval growing to 30 s, then it came back
by itself 30 s after the bridge did. On 1.8.2 the first of those failures is
the last thing the loop ever does.

Worth recording from the same session: a bridge that *reboots* rather than
disappearing is a different case. It sends no FIN, so the loss is only noticed
by TCP keepalive about 60 s later, by which time the bridge is back and the
first reconnect succeeds. 1.8.2 survives that, which is why the bug needs a
peer that is still gone when the retry runs, and why the reporter's
cleanly-closing `stream_server` hit it and a plain reboot here did not.

## Sources

- Issue #42, with the reporter's logs, the independent `CO_RD_VERSION` capture
  and the per-hour count of reconnect attempts.
