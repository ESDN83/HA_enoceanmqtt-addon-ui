"""
Read the device lists of the add-ons people switch from (ADR-0020).

- ChristopheHD enocean-mqtt: the INI file `enoceanmqtt.devices`, by default
  `/config/enoceanmqtt.devices`, which this add-on can read through `config:rw`.
- EnOcean MQTT Slim (our own predecessor, archived): `{"devices": [...]}` from
  its `/api/devices`, or its raw `/data/devices.json` keyed by address.

Both parsers only build candidate devices; nothing is written here. The UI
shows them for review and creates each chosen one through the normal
POST /api/devices, so name checks and discovery stay in one place.
"""

import configparser
import json
import re
from typing import Any, Dict, List, Tuple

CHRISTOPHEHD_DEFAULT_FILE = "/config/enoceanmqtt.devices"
# The default Supervisor role may read one add-on's info but not list them
# all, so Slim is looked up by slug: the store installs it from GitHub under
# the first 8 hex of sha1(repo URL), a local copy is "local_".
SLIM_SLUGS = ("4b60c4f5_enocean-mqtt-slim", "local_enocean-mqtt-slim")

_HEX8 = re.compile(r"^[0-9A-F]{1,8}$")
_HEX2 = re.compile(r"^[0-9A-F]{1,2}$")
_EEP = re.compile(r"^([0-9A-F]{2})-([0-9A-F]{2})-([0-9A-F]{2})$")


def _hex(value: Any) -> str:
    v = str(value or "").strip().upper()
    if v.startswith("0X"):
        v = v[2:]
    return v


def _address(value: Any) -> str:
    """'0xabadc0de', 'ABADC0DE', '5834fa4' -> '0x05834FA4'; '' if not hex."""
    v = _hex(value)
    return f"0x{v.zfill(8)}" if _HEX8.match(v) else ""


def _candidate(name: str, address: str, rorg: str, func: str, type_: str,
               sender_id: str = "", **extra) -> Dict[str, Any]:
    d = {
        "name": name,
        "address": address,
        "rorg": rorg,
        "func": func.zfill(2) if func else "",
        "type": type_.zfill(2) if type_ else "",
        "sender_id": sender_id,
    }
    d.update(extra)
    return d


def parse_christophehd(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Parse an `enoceanmqtt.devices` INI file.

    Returns (devices, skipped). A section is skipped with a reason when it
    is ignored, defined only by `model =` (no EEP to map from), or invalid.
    """
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"),
                                   strict=False, interpolation=None)
    cp.read_string(text)

    devices, skipped = [], []
    for section in cp.sections():
        if section.upper() == "CONFIG":
            continue
        s = cp[section]
        if str(s.get("ignore", "")).strip() not in ("", "0"):
            skipped.append({"name": section, "reason": "ignored"})
            continue
        address = _address(s.get("address", ""))
        if not address:
            skipped.append({"name": section, "reason": "no_address"})
            continue
        rorg, func, type_ = _hex(s.get("rorg")), _hex(s.get("func")), _hex(s.get("type"))
        if not (rorg and func and type_):
            reason = "model_only" if s.get("model") else "no_eep"
            skipped.append({"name": section, "reason": reason,
                            "address": address, "model": s.get("model", "")})
            continue
        if not (_HEX2.match(rorg) and _HEX2.match(func) and _HEX2.match(type_)):
            skipped.append({"name": section, "reason": "no_eep", "address": address})
            continue
        sender = _address(s.get("sender", "") or s.get("sender_id", ""))
        devices.append(_candidate(section, address, rorg, func, type_, sender))
    return devices, skipped


def parse_slim(data: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Parse Slim's device list: `{"devices": [...]}`, a bare list, or the
    `devices.json` dict keyed by address. Each entry has `id` and `eep`
    ("A5-04-01"), plus `name` and `manufacturer`."""
    if isinstance(data, (bytes, str)):
        data = json.loads(data)
    if isinstance(data, dict) and isinstance(data.get("devices"), list):
        entries = data["devices"]
    elif isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = [dict(v, id=v.get("id", k)) for k, v in data.items() if isinstance(v, dict)]
    else:
        raise ValueError("not a Slim device list")

    devices, skipped = [], []
    for e in entries:
        if not isinstance(e, dict):
            continue
        address = _address(e.get("id", ""))
        name = str(e.get("name") or "").strip() or (address[2:].lower() if address else "")
        if not address:
            skipped.append({"name": name or "?", "reason": "no_address"})
            continue
        m = _EEP.match(str(e.get("eep", "")).strip().upper())
        if not m:
            skipped.append({"name": name, "reason": "no_eep", "address": address})
            continue
        devices.append(_candidate(name, address, *m.groups(),
                                  manufacturer=str(e.get("manufacturer") or "")))
    return devices, skipped


def detect_and_parse(raw: bytes) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, str]]]:
    """Tell an uploaded file's format apart by content, not by its name."""
    text = raw.decode("utf-8-sig", errors="replace")
    try:
        data = json.loads(text)
    except ValueError:
        data = None  # an INI section header "[x]" also starts with "["
    if data is not None:
        return ("slim",) + parse_slim(data)
    try:
        return ("christophehd",) + parse_christophehd(text)
    except configparser.Error as e:
        raise ValueError(f"unknown format: {e}")


def annotate(candidates: List[Dict[str, Any]], device_manager, eep_manager) -> None:
    """Mark each candidate for the review table, in place:
    `eep` (A5-04-01), `eep_known`, `exists` (a device with this name or this
    address and EEP is already configured), and a unique free `name`."""
    taken = set(device_manager.devices.keys()) if device_manager else set()
    for c in candidates:
        c["eep"] = f"{c['rorg']}-{c['func']}-{c['type']}"
        c["eep_known"] = bool(eep_manager and eep_manager.get_profile(c["eep"]))
        same = []
        if device_manager:
            same = [d for d in device_manager.get_devices_by_address(c["address"])
                    if f"{d.rorg}-{d.func}-{d.type}".upper() == c["eep"]]
        c["exists"] = bool(same)
        # Names are MQTT topic segments: no / + #.
        base = re.sub(r"[/+#]", "_", c["name"]).strip() or c["address"][2:].lower()
        name, n = base, 2
        while name in taken:
            name, n = f"{base}_{n}", n + 1
        c["name"] = name
        taken.add(name)


def match_old_entity(topic: str, payload: bytes, discovery_prefix: str,
                     addresses: set) -> Dict[str, str]:
    """Is this retained discovery message an entity of Slim or ChristopheHD
    for a device that is already configured here? Returns its details, or {}.

    Both old add-ons publish `<prefix>/<component>/<unique_id>/config`, three
    levels; this app publishes `<prefix>/<component>/enocean/<uid>/config`,
    four. The depth alone keeps our own entities out. On top, the unique_id
    must start with `enocean_` and carry the address of a configured device
    (`addresses`: 8 lowercase hex), so an old entity of a device that was not
    imported is never touched.
    """
    parts = topic.split("/")
    if topic.startswith(discovery_prefix + "/"):
        parts = topic[len(discovery_prefix) + 1:].split("/")
    else:
        return {}
    if len(parts) != 3 or parts[2] != "config" or not payload:
        return {}
    try:
        cfg = json.loads(payload)
    except ValueError:
        return {}
    uid = str(cfg.get("unique_id", "")) if isinstance(cfg, dict) else ""
    if not uid.startswith("enocean_"):
        return {}
    hit = next((t for t in uid.lower().split("_") if t in addresses), "")
    if not hit:
        return {}
    state = str(cfg.get("state_topic", ""))
    return {
        "topic": topic,
        "unique_id": uid,
        "component": parts[0],
        "name": str(cfg.get("name") or ""),
        "device": str((cfg.get("device") or {}).get("name") or ""),
        "address": "0x" + hit.upper(),
        "source": "slim" if state.startswith("enocean/") else "christophehd",
        "key": field_key(cfg, uid, hit),
    }


# ChristopheHD reads RSSI and the receive time from its own pseudo-fields;
# this app and Slim call them rssi and last_seen.
# Slim's A5-04-02 profile calls humidity HM where the EEP.xml says HUM.
_FIELD_ALIASES = {"_rssi_": "rssi", "_date_": "last_seen", "hm": "hum"}

_TEMPLATE_FIELD = re.compile(r"""value_json(?:\.(\w+)|\[['"](\w+)['"]\])""")


def field_key(cfg: Dict[str, Any], uid: str, address: str) -> str:
    """Which value an entity shows, as a lowercase key (`tmp`, `rssi`).

    The three apps name entities differently (Slim `enocean_<addr>_TMP`,
    ChristopheHD `..._tempC`, this app `enocean_<eep>_<addr>_TMP`), but all of
    them read one field of the same decoded telegram, so the field in the
    value_template is what pairs an old entity with its new one. Without a
    template, the unique_id after the address (and a sender, for ChristopheHD)
    is used.
    """
    m = _TEMPLATE_FIELD.search(str(cfg.get("value_template") or ""))
    if m:
        key = (m.group(1) or m.group(2)).lower()
        return _FIELD_ALIASES.get(key, key)
    tokens = uid.lower().split("_")
    if address in tokens:
        tokens = tokens[tokens.index(address) + 1:]
        if tokens and (tokens[0] == "none" or re.fullmatch(r"[0-9a-f]{8}", tokens[0])):
            tokens = tokens[1:]  # ChristopheHD: sender, or NONE
    return "_".join(tokens)


def match_own_entity(topic: str, payload: bytes, discovery_prefix: str,
                     addresses: set) -> Dict[str, str]:
    """An entity this app publishes (`<prefix>/<component>/enocean/<uid>/config`)
    for one of `addresses`, with the same `key` as match_old_entity, or {}."""
    if not topic.startswith(discovery_prefix + "/") or not payload:
        return {}
    parts = topic[len(discovery_prefix) + 1:].split("/")
    if len(parts) != 4 or parts[1] != "enocean" or parts[3] != "config":
        return {}
    try:
        cfg = json.loads(payload)
    except ValueError:
        return {}
    uid = str(cfg.get("unique_id", "")) if isinstance(cfg, dict) else ""
    hit = next((t for t in uid.lower().split("_") if t in addresses), "")
    if not hit:
        return {}
    return {"unique_id": uid, "component": parts[0], "address": "0x" + hit.upper(),
            "key": field_key(cfg, uid, hit)}


def pair_entities(old: List[Dict[str, str]], own: List[Dict[str, str]]) -> None:
    """Give each old entity the new entity that takes over its entity ID, in
    place: `new_unique_id`, or `pair_note` saying why there is none.

    A pair needs the same address, the same field and the same component
    (the domain is part of an entity ID, a sensor cannot become a
    binary_sensor). ChristopheHD offers a raw and a rounded entity for some
    fields; the rounded one wins. Anything still ambiguous is left alone.
    """
    for o in old:
        o["new_unique_id"], o["pair_note"] = "", ""
    by_key: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for o in old:
        by_key.setdefault((o["address"], o["key"]), []).append(o)
    for n in own:
        group = by_key.get((n["address"], n["key"]), [])
        same = [o for o in group if o["component"] == n["component"]]
        if not same:
            for o in group:
                o["pair_note"] = o["pair_note"] or "other_type"
            continue
        if len(same) > 1:
            cooked = [o for o in same if not o["unique_id"].lower().endswith("_raw")
                      and not o["name"].lower().endswith("_raw")]
            same = cooked if len(cooked) == 1 else same
        if len(same) > 1:
            for o in same:
                o["pair_note"] = "ambiguous"
            continue
        same[0]["new_unique_id"], same[0]["pair_note"] = n["unique_id"], ""
    for o in old:
        if not o["new_unique_id"] and not o["pair_note"]:
            o["pair_note"] = "no_match"
