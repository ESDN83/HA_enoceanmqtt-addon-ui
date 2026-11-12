# 0049. Stay on raw TCP, do not adopt ESPHome serial_proxy

Status: accepted (2026-11-12). No code change; recorded so the evaluation is
not repeated from memory.

## Context

Home Assistant 2026.11 introduced the ESPHome `serial_proxy` component (by
@puddly). The release blog says an ESPHome device can "share one of their
serial ports over your network, so an integration can reach a serial-connected
device", that "Zigbee Home Automation can use it for a Zigbee adapter plugged
into an ESPHome device", and that it "keeps working when you move that adapter
to another ESPHome device".

That reads like it could replace how this add-on reaches the production USB 300,
which sits behind our own ESP bridge (`esp-ha-usb-gateway`) on
192.168.1.122:8880 as a raw TCP port. Two hopes in particular: configuring the
transceiver without a hardcoded IP, and getting reconnect handling for free.

Checked against the ESPHome docs and the component source on 2026-11-12:

- `serial_proxy` exposes the UART **through the ESPHome Native API**, not as a
  raw socket. The component declares `DEPENDENCIES = ["api", "uart"]`. The
  Native API is protobuf on port 6053 and normally Noise-encrypted.
- This add-on opens a plain socket (`serial_handler.py`, `_connect_tcp`) and
  reads ESP3 frames off the stream. It cannot consume a protobuf API.
- The "port shows up when you set up the integration" behaviour is Home
  Assistant **integration** discovery. HA already knows ESPHome devices through
  the ESPHome integration and offers their proxied ports to integrations such
  as ZHA. This add-on is a separate container and does not take part in that,
  so the IP would not go away for us.
- The same applies to "keeps working when you move that adapter": that is ZHA's
  config entry binding to the adapter identity instead of `host:port`. An
  add-on inherits none of it.
- A proxied port accepts one subscriber at a time.
- The docs mark the component experimental, with an API that may still change.
- Reconnect is not an open problem here. The read loop already has exponential
  backoff, `KEEPALIVE_MISSES_BEFORE_RECONNECT` (issue #51) and accept-then-FIN
  handling (issue #41).

A second finding from the same check: ESPHome now ships `usb_host`, `usb_uart`
and `usb_cdc_acm`. `usb_uart` covers CDC_ACM, CH34X, CH340 and CP210X and has a
`claim_comm_interface` option for the CDC communications interface. It does
**not** cover FTDI, and the production USB 300 is FTDI, so our own `usb_bridge`
component stays necessary.

## Decision

Keep reaching the transceiver over the raw TCP port exposed by our own ESP
bridge. Do not add an `aioesphomeapi` client to the add-on.

## Consequences

- The transceiver host and port stay explicit configuration (`tcp_port`), as in
  ADR-0001 for the local serial case.
- No protobuf dependency, no API encryption key to manage in the add-on, no
  single-subscriber limit, no exposure to an experimental API.
- We give up the IP-free setup and the move-the-adapter behaviour. Both are
  integration-level features that an add-on cannot get without becoming an
  integration, which is out of scope.

## When to revisit

Re-check if any of these change:

- `serial_proxy` gains a raw TCP or RFC2217 listener alongside the Native API,
  which would make it consumable by a plain socket client.
- Home Assistant exposes proxied serial ports to add-ons, for example through a
  Supervisor service or discovery message, rather than to integrations only.
- `usb_uart` upstream gains FTDI support, which would make our own `usb_bridge`
  component redundant for the production transceiver and change the trade-off
  for the whole ESP bridge.
- The experimental marker comes off and the API is declared stable.
