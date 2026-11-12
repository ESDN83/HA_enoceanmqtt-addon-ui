# 0051. Remote Commissioning through ESP3 remote management packets

Status: proposed (beta).

## Context

ADR-0047 built the SYS_EX telegrams of Remote Commissioning in the app and
sent them as addressed RADIO_ERP1 packets. A real OPUS BRiDGE 563.010 sent
nothing back, not even to the ping, with the full-length telegrams of
1.8.7-beta4 (forum 1026367, 2026-11-12). The app's bit packing has only ever
been checked against the fake transceiver, which was built from the same
reading of the specification.

FHEM (10_EnOcean.pm, 00_TCM.pm) does not build SYS_EX telegrams at all: it
sends ESP3 REMOTE_MAN_COMMAND (packet type 7: function, manufacturer ID,
message data; optional destination, source 0 = chip ID, dBm 0xFF, send with
delay) and receives answers as packet type 7, decoded by the module. The
command content (function 0x001 with the 4-byte code, 0x006, manufacturer
0x7FF, addressed to the device) is the same as ours. The QR identifier 11Z
is the "ReMan Security Code" in the EnOcean labeling specification v1.4.

## Decision

- Commands go out as packet type 7 first, source 0 like FHEM.
- When the module answers RET_NOT_SUPPORTED, another error, or nothing, the
  app falls back to its own SYS_EX telegrams for the rest of its run. A TCP
  gateway that does not pass packet type 7 lands there.
- Packet type 7 answers are handled whichever way the command went out, in
  case a module decodes incoming remote management telegrams by itself.
- The log names the path used; the code stays out of every log line.

## Consequences

- The app's SYS_EX format is no longer in the path on a USB300/TCM310.
- Still unconfirmed on a real device.
