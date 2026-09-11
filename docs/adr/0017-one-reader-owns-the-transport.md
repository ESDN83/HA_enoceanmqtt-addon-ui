# 0017. Exactly one read loop owns the transceiver at a time

Status: accepted (v1.8.2-beta4).

## Context

`connect()` assigned `self._read_task = asyncio.create_task(self._read_loop())`
without touching what the attribute already pointed at. The old loop kept
running, and because `_serial_read` resolves `self._socket` on every call, it
kept reading from whatever transport was current, including the one the new
loop had just opened.

Two readers on one socket do not duplicate telegrams, they destroy them. Each
`recv` hands a slice of the byte stream to whichever loop asked first, so
neither ever assembles a whole ESP3 frame. Reception dies silently while
transmission, which does not go through the read loop, keeps working. The
symptom is an add-on whose entities freeze while actuators still switch.

Three paths reached that state, all reported in #41:

- `POST /api/system/restart` tore the old handler down only `if
  serial_handler.is_connected`, and `is_connected` is False for as long as the
  read loop sits between reconnect attempts. In exactly that window the
  teardown was skipped and `connect()` added a second loop.
- `POST /api/gateway/test-connection` calls `connect()` under the same
  condition.
- `connect()` raises when the base ID read times out, but by then it has
  already started a loop. Every retry from `_serial_background_connect` added
  another one.

The reporter's log shows the signature: several "Serial reader: still waiting
for data" lines with the same elapsed time and divergent packet counts, growing
by one on each reconnect, while a TCP capture proved the transceiver was
sending complete frames the whole time.

## Decision

- **Every path that opens a transport stops the previous reader first.**
  `connect()` and `disconnect()` both go through `_stop_reader()`, which
  cancels the task and awaits it, so a caller can invoke `connect()` on a
  handler in any state.
- **A generation counter is the second lock.** `_stop_reader` bumps it, each
  loop is started with the value it was born under, and a loop that finds the
  counter moved on stops by itself. Cancellation alone relies on every future
  caller remembering the rule; the counter does not.
- **`/restart` tears down unconditionally**, rather than only when the handler
  reports itself connected.
- **The generation is in the log line**, `Serial reader #3: still waiting for
  data`, so two readers are one grep away instead of an inference from packet
  counts.

## Consequences

- `connect()` is idempotent: calling it on a live handler reconnects rather
  than duplicating. That is what the two API endpoints always assumed.
- A cancelled loop can still lose the bytes of the one `recv` already running
  in the executor thread, which no amount of task cancellation can take back.
  That costs at most one frame at teardown, against a reception that never
  recovers.
- Duplicating the "Connected to EnOcean transceiver" line from `main.py` next
  to the one `connect()` already logs was removed in the same change. It reads
  like two connections, which is the same confusion the duplicated MQTT connect
  message caused once before.

## Sources

- Issue #41, with the reporter's reader-count log and TCP capture.
