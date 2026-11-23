"""
Home Assistant mappings for profiles that decoded but had no entities.
ADR-0055. Fields from EEP.xml; scalings that EEP.xml leaves out
(D2-06-01, A5-13-06, A5-09-0C) checked against FHEM 10_EnOcean.pm.

A value the telegram does not carry renders None (unknown) or '' (keep the
last value), never a template error.
"""

from typing import Any, Dict

# Profiles whose telegrams carry different fields each time: the last state
# is merged in, or every telegram would blank the other fields.
MERGE_EEPS = {"A5-13-01", "A5-13-02", "A5-13-03", "A5-13-04", "A5-13-05", "A5-13-06", "D2-06-01"}


def merge_state(last: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = {k: v for k, v in (last or {}).items() if not k.startswith("_")}
    # An enum code without a description (a reserved value) has no _text:
    # the old text must not stay next to the new code.
    for key in payload:
        merged.pop(f"{key}_text", None)
    merged.update(payload)
    return merged


def _if(field, expr, other="None"):
    return f"{{{{ ({expr}) if value_json.{field} is defined else {other} }}}}"


def _s(name, template, unit=None, dev=None, state="measurement", diag=False, icon=None):
    d: Dict[str, Any] = {"component": "sensor", "name": name, "value_template": template}
    for key, value in (("unit_of_measurement", unit), ("device_class", dev),
                       ("state_class", state), ("icon", icon)):
        if value:
            d[key] = value
    if diag:
        d["entity_category"] = "diagnostic"
    return d


def _b(name, template, dev=None, diag=False):
    d: Dict[str, Any] = {"component": "binary_sensor", "name": name, "value_template": template}
    if dev:
        d["device_class"] = dev
    if diag:
        d["entity_category"] = "diagnostic"
    return d


def _v(field):
    return _if(field, f"value_json.{field}")


def _temp(name="Temperature"):
    return _s(name, _v("TMP"), "°C", "temperature")


_HUM = _s("Humidity", _v("HUM"), "%", "humidity")
# The knob position as sent (0-255): what it means is up to the room unit.
_SP = _s("Set Point", _v("SP"), icon="mdi:tune-vertical")
# EEP.xml: 0 = button pressed
_OCC = _b("Occupancy Button", _if("OCC", "1 - value_json.OCC"))

_SCM = "[0.01, 0.1, 1, 10][value_json.SCM | int]"
_DIV = "[1, 10, 100, 1000][value_json.DIV | int]"


def _voc(unit):
    return (f"{{{{ (value_json.Conc * {_SCM}) | round(2) "
            f"if value_json.Conc is defined and value_json.Unit == {unit} else '' }}}}")


def _mr(dt):
    return f"{{{{ (value_json.MR / {_DIV}) | round(3) if value_json.DT is defined and value_json.DT == {dt} else '' }}}}"


def _klx(field):
    return _s({"SNW": "Sun West", "SNS": "Sun South", "SNE": "Sun East"}[field],
              _if(field, f"(value_json.{field} * 1000) | round(0)"), "lx", "illuminance")


_SUN = {f: _klx(f) for f in ("SNW", "SNS", "SNE")}
_DATE = {"DATE": _s("Date", _if("DY", "'%04d-%02d-%02d' | format(value_json.YR | int, value_json.MTH | int, value_json.DY | int)"),
                    dev="date", state=None)}
# 12 hour format (TMF 1) with AM/PM to 24 hours
_HOUR = "((value_json.HR | int) % 12 + (12 if value_json.AMPM == 1 else 0)) if value_json.TMF == 1 else (value_json.HR | int)"
_TIME = {"TIME": _s("Time", _if("HR", f"'%02d:%02d:%02d' | format({_HOUR}, value_json.MIN | int, value_json.SEC | int)"),
                    state=None, icon="mdi:clock-outline"),
         "WDY": _s("Weekday", _if("WDY_text", "value_json.WDY_text"), state=None, icon="mdi:calendar")}
_DIRECTION = {"ELV": _s("Sun Elevation", _v("ELV"), "°", icon="mdi:weather-sunny"),
              "AZM": _s("Sun Azimuth", _v("AZM"), "°", icon="mdi:compass")}
# 12 bits over -90..90 and -180..180 degrees
_POSITION = {
    "LAT": _s("Latitude", _if("LAT_LSB", "((value_json.LAT_MSB * 256 + value_json.LAT_LSB) * 180 / 4095 - 90) | round(3)"),
              "°", state=None, diag=True),
    "LOT": _s("Longitude", _if("LOT_LSB", "((value_json.LOT_MSB * 256 + value_json.LOT_LSB) * 360 / 4095 - 180) | round(3)"),
              "°", state=None, diag=True)}
_WEATHER = {
    "TMP": _temp("Outdoor Temperature"),
    "WND": _s("Wind Speed", _v("WND"), "m/s", "wind_speed"),
    "DWS": _s("Dawn Sensor", _v("DWS"), "lx", "illuminance"),
    "RAN": _b("Rain", _v("RAN"), "moisture"),
    "DN": _s("Day/Night", _if("DN", "'night' if value_json.DN == 1 else 'day'"), state=None, icon="mdi:theme-light-dark"),
}


def _flag(field):
    """0 no, 1 yes, 14 invalid, 15 not supported"""
    return _if(field, f"value_json.{field} if value_json.{field} in (0, 1) else None")


def _count(name, field):
    return _s(name, _v(field), state="total_increasing", diag=True)


MAPPINGS: Dict[str, Dict[str, Any]] = {
    "A5-04-04": {"TMP": _temp(), "HUM": _HUM},
    "A5-06-02": {
        "ILL": _s("Illuminance", _if("RS", "value_json.ILL2 if value_json.RS == 1 else value_json.ILL1"),
                  "lx", "illuminance"),
        "SVC": _s("Supply Voltage", _v("SVC"), "V", "voltage", diag=True)},
    "A5-09-0C": {
        "VOC_PPB": _s("VOC (ppb)", _voc(0), "ppb", "volatile_organic_compounds_parts"),
        "VOC_UG": _s("VOC (µg/m³)", _voc(1), "µg/m³", "volatile_organic_compounds"),
        "VOC_ID": _s("VOC Type", _if("VOC_ID", "value_json.VOC_ID_text if value_json.VOC_ID_text is defined else value_json.VOC_ID"),
                     state=None, diag=True)},
    "A5-10-03": {"TMP": _temp(), "SP": _SP},
    "A5-10-05": {"TMP": _temp(), "SP": _SP, "OCC": _OCC},
    "A5-10-10": {"TMP": _temp(), "HUM": _HUM, "SP": _SP, "OCC": _OCC},
    "A5-10-12": {"TMP": _temp(), "HUM": _HUM, "SP": _SP},
    "A5-12-00": {
        "MR": _s("Counter", _mr(0), state="total_increasing", icon="mdi:counter"),
        "CUR": _s("Current Value", _mr(1), "1/s", icon="mdi:speedometer"),
        "CH": _s("Channel", _v("CH"), state=None, diag=True)},
    "A5-13-01": {**_WEATHER, **_SUN, **_DATE, **_TIME, **_DIRECTION, **_POSITION},
    "A5-13-02": dict(_SUN),
    "A5-13-03": dict(_DATE),
    "A5-13-04": dict(_TIME),
    "A5-13-05": dict(_DIRECTION),
    "A5-13-06": dict(_POSITION),
    "A5-30-04": {
        "DI0": _b("Input 0", _v("DI0"), "power"),
        "DI1": _b("Input 1", _v("DI1"), "power"),
        "DI2": _b("Input 2", _v("DI2"), "power"),
        "DV0": _s("Digital Value", _v("DV0"), icon="mdi:numeric")},
    "D2-03-0A": {"BATT": _s("Battery", _v("BATT"), "%", "battery", diag=True)},
    "D2-06-01": {
        # handle down = closed, up = tilted, left or right = open
        "WIN": _b("Window", _if("HP", "{1: 1, 2: 0, 3: 1, 4: 1}.get(value_json.HP)"), "window"),
        "WS": _b("Window Tilted", _if("WS", "{1: 0, 2: 1}.get(value_json.WS)")),
        "HP": _s("Handle", _if("HP", "{1: 'up', 2: 'down', 3: 'left', 4: 'right'}.get(value_json.HP)"),
                 state=None, icon="mdi:window-closed-variant"),
        "M": _b("Motion", _flag("M"), "motion"),
        "BAL": _b("Burglary Alarm", _flag("BAL"), "safety"),
        "PPAL": _b("Protection Plus Alarm", _flag("PPAL"), "safety"),
        "T": _s("Temperature", _if("T", "(value_json.T * 80 / 250 - 20) | round(1) if value_json.T <= 250 else None"),
                "°C", "temperature"),
        "H": _s("Humidity", _if("H", "value_json.H / 2 if value_json.H <= 200 else None"), "%", "humidity"),
        "I": _s("Illuminance", _if("I", "value_json.I if value_json.I <= 60000 else None"), "lx", "illuminance"),
        "BS": _s("Battery", _if("BS", "value_json.BS * 5 if value_json.BS <= 20 else None"), "%", "battery", diag=True),
        "HMC": _count("Handle Movements Closed", "HMC"),
        "HMO": _count("Handle Movements Opened", "HMO"),
        "HMT": _count("Handle Movements Tilted", "HMT"),
        "WT": _count("Window Tilts", "WT")},
    "F6-04-01": {"KC": _b("Key Card", _if("KC", "1 if value_json.KC == 112 else 0"), "presence")},
    "F6-05-01": {"WAS": _b("Water Leak", _if("WAS", "1 if value_json.WAS == 17 else 0"), "moisture")},
}
