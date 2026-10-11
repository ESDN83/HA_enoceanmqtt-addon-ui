# 0025. Default mappings are checked against EEP.xml

Status: proposed (v1.8.4-beta10).

## Context

Three profiles in one week read fields their profile does not have
(ADR-0022 PIRS, ADR-0024 window handle). A script compared every default
mapping with the bundled EEP.xml: seven more profiles had the same problem.
Most came from the arno0392 fork. Before changing them, three sources were
compared for each profile: the bundled EEP.xml, the current upstream
(ChristopheHD/enocean, last changed 2026-10-08, only D2-50-00 differs) and
arno's own EEP.xml. All three agree, and arno's code has no renaming that
would explain the names, so the mappings never matched.

Also found: every D2-01 sensor-mode mapping set `payload_on: "100"`, which
the generic binary_sensor code overwrote with `"1"`, so such an output never
showed on.

## Decision

Following EEP.xml, keeping each mapping's key, name and class so entity IDs
stay:

- A5-06-01 Illuminance: ILL1 or ILL2, as RS selects.
- A5-09-04 CO2 reads Conc; temperature and humidity only when the sensor
  flags them as fitted (TSN, HSN).
- A5-09-05 VOC reads Conc with the ppb device class, plus a VOC Type
  sensor. Temperature and humidity are retired, the profile has neither.
- A5-12-01: MR divided by DIV; Energy in kWh when DT is 0, Current Power in W
  when DT is 1. The other kind keeps the last value.
- A5-14-01: a Contact (window) entity from CT; Vibration is retired.
- A5-30-02 Input 0 reads IPS.
- D2-01 sensor mode: any output level above 0 is on, 127 (not valid) is
  skipped.

Profiles without a definition in EEP.xml (A5-09-02, A5-12-02/03, A5-14-05,
A5-30-01, D2-01-02/06/11, D2-05-01, F6-03-01/02) are not touched: nothing
decodes them without a custom profile, and a custom profile can bring its
own mapping.

## Consequences

- These devices show values without user action.
- A5-12-01 Energy changes unit from Wh to kWh; Home Assistant's statistics
  may ask to fix the unit once. The old values were raw counts, not Wh.
- A future default mapping should be run through the same check.
