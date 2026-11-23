# 0055. Entities for profiles that had none

Status: proposed (beta).

## Context

19 profiles of EEP.xml decoded but had no Home Assistant mapping.

## Decision

- Mappings in `core/profile_mappings.py`, written from EEP.xml. Scalings
  EEP.xml lacks (D2-06-01 temperature and humidity, A5-13-06 position,
  A5-09-0C multiplier) checked against FHEM 10_EnOcean.pm. No code or mapping
  from HA_enoceanmqtt (GPL-3.0).
- A5-13: the identifier (ID) selects the layout, and A5-13-02 to 06 decode
  with A5-13-01, which alone describes all of them. Telegrams of A5-13 and
  D2-06-01 carry different fields each time, so the last state is merged in.
- D2-03-0A and D2-06-01 buttons follow the rocker event model (ADR-0042).
- D2-50-00 gets INT, EXHT and HBS at the offsets FHEM reads; raw 0 (-64 °C)
  is shown as unknown.

## Consequences

- Set points stay raw (0-255): their meaning depends on the room unit.
- Not confirmed on hardware.
