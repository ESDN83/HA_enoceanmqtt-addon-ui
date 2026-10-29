# 0038. TCP idle keepalive, commands wait for a reconnect, own echoes ignored

Status: proposed (v1.8.5-beta15).

## Context

Issue #51 (Symcon EnOcean LAN gateway, TCM515, 13 h debug log): the gateway
closes a TCP connection after 300 s without data (its "Inactivity Timer").
The only regular traffic was the 300 s energy poll, so the connection was
dropped about 0.7 s before each poll, and the poll fell into the 1 s
reconnect gap: skipped without a log line. An HA command in that gap was
dropped with a warning. TCP keepalive carries no data and does not count
for such gateways.

The same log showed most "Unknown device" lines coming from the app's own
sender IDs (base ID + offset), 5-60 ms after its own transmit with identical
data: a repeater sending them back.

## Decision

- After 60 s without transmitting on TCP, the app sends CO_RD_VERSION.
  Counted from the last transmit, not receive, because a gateway may count
  only what it receives. Two unanswered in a row shut the socket down, and
  the read loop reconnects as for any lost transport.
- A command or energy poll that finds the transport down waits up to 5 s for
  the reconnect, then is dropped with a warning.
- A telegram whose sender is in base ID .. base ID + 0x7F and is not a
  configured device is our own, repeated: debug log only, not in the
  telegram buffer or the unknown device list.

## Consequences

- One small ESP3 command a minute on an otherwise idle TCP link.
- A serial (USB) transceiver is unchanged: no keepalive.
- A command may now be delayed by up to 5 s instead of dropped.
