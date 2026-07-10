"""
Mapping Manager - Handles EEP to MQTT/HA entity mappings

Generates Home Assistant MQTT discovery configurations compatible with
ChristopheHD/HA_enoceanmqtt-addon discovery format.

Discovery UID format: enocean_{EEP}_{ADDR}_{SHORTCUT}
  e.g., enocean_A53003_05834FA4_DI0
With sender: enocean_{EEP}_{ADDR}_{SENDER}_{SHORTCUT}
  e.g., enocean_A53003_05834FA4_AABBCCDD_DI0
"""

import os
import logging
from typing import Dict, List, Optional, Any
import yaml
import aiofiles

logger = logging.getLogger(__name__)


def _rocker_button_binary_sensors() -> Dict[str, Any]:
    """Build the four per-button binary_sensor mappings for an RPS rocker
    switch (F6-02-01 / F6-02-02).

    Each button is ON while it is physically held (Energy Bow EB == 1 and the
    rocker field points at that button) and OFF on release (EB == 0). Both the
    first action (R1) and the optional second action (R2 when SA == 1) are
    checked, so a two-button press lights up both sensors.

    R1/R2 button encoding per EEP F6-02-0x:
        0 = AI (Rocker A, bottom)   1 = AO (Rocker A, top)
        2 = BI (Rocker B, bottom)   3 = BO (Rocker B, top)
    """
    buttons = {"AI": 0, "AO": 1, "BI": 2, "BO": 3}
    mapping: Dict[str, Any] = {}
    for shortcut, code in buttons.items():
        mapping[shortcut] = {
            "component": "binary_sensor",
            "name": f"Button {shortcut}",
            "icon": "mdi:gesture-tap-button",
            "value_template": (
                "{{ 1 if value_json.EB == 1 and "
                f"(value_json.R1 == {code} or "
                f"(value_json.SA == 1 and value_json.R2 == {code})) else 0 }}}}"
            ),
        }
    return mapping


# Default mappings for common EEP profiles
DEFAULT_MAPPINGS = {
    # 4BS Temperature Sensors (A5-02-xx)
    "A5-02-05": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "value_template": "{{ value_json.TMP }}"
        }
    },
    # 4BS Temperature and Humidity (A5-04-01)
    "A5-04-01": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "°C"
        },
        "HUM": {
            "component": "sensor",
            "name": "Humidity",
            "device_class": "humidity",
            "unit_of_measurement": "%"
        }
    },
    # 4BS Occupancy Sensor (A5-07-01)
    "A5-07-01": {
        "PIR": {
            "component": "binary_sensor",
            "name": "Occupancy",
            "device_class": "occupancy"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    # 4BS Digital Input (A5-30-03)
    "A5-30-03": {
        "DI0": {
            "component": "binary_sensor",
            "name": "Input 0",
            "device_class": "power"
        },
        "DI1": {
            "component": "binary_sensor",
            "name": "Input 1",
            "device_class": "power"
        },
        "DI2": {
            "component": "binary_sensor",
            "name": "Input 2",
            "device_class": "power"
        },
        "DI3": {
            "component": "binary_sensor",
            "name": "Input 3",
            "device_class": "power"
        }
    },
    # 1BS Contact Sensor (D5-00-01)
    "D5-00-01": {
        "CO": {
            "component": "binary_sensor",
            "name": "Contact",
            "device_class": "door"
        }
    },
    # RPS Rocker Switch, 2 Rockers (F6-02-01)
    # Keeps the existing Rocker A/B text sensors + Energy Bow (backwards
    # compatible) and adds one momentary binary_sensor per button (AI/AO/BI/BO).
    "F6-02-01": {
        "R1": {
            "component": "sensor",
            "name": "Rocker A",
            "icon": "mdi:gesture-tap-button",
            "value_template": "{{ value_json.R1_text }}"
        },
        "R2": {
            "component": "sensor",
            "name": "Rocker B",
            "icon": "mdi:gesture-tap-button",
            "value_template": "{{ value_json.R2_text }}"
        },
        "EB": {
            "component": "binary_sensor",
            "name": "Energy Bow",
            "device_class": "power"
        },
        **_rocker_button_binary_sensors()
    },
    # RPS Rocker Switch, 2 Rockers, Light and Blind Control (F6-02-02)
    # e.g. Eltako FT55. One momentary binary_sensor per button (AI/AO/BI/BO)
    # plus Rocker A/B text sensors for the last-pressed button.
    "F6-02-02": {
        "R1": {
            "component": "sensor",
            "name": "Rocker A",
            "icon": "mdi:gesture-tap-button",
            "value_template": "{{ value_json.R1_text }}"
        },
        "R2": {
            "component": "sensor",
            "name": "Rocker B",
            "icon": "mdi:gesture-tap-button",
            "value_template": "{{ value_json.R2_text }}"
        },
        **_rocker_button_binary_sensors()
    },
    # VLD Electronic Switch (D2-01-0F)
    "D2-01-0F": {
        "CMD": {
            "component": "switch",
            "name": "Switch",
            "icon": "mdi:power"
        },
        "OV": {
            "component": "sensor",
            "name": "Output Value",
            "unit_of_measurement": "%"
        }
    },
    # VLD Blinds Control (D2-05-00)
    "D2-05-00": {
        "POS": {
            "component": "cover",
            "name": "Position",
            "device_class": "blind"
        },
        "ANG": {
            "component": "sensor",
            "name": "Angle",
            "unit_of_measurement": "°"
        }
    },
    # 4BS Temperature Sensors (A5-02 family) — from arno0392 fork
    "A5-02-01": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-02": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-03": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-04": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-06": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-07": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-08": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-09": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-0A": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-0B": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-10": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-11": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-12": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-13": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-14": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-15": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-16": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-17": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-18": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-19": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-1A": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-1B": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-20": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-02-30": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    # 4BS Temperature and Humidity (A5-04) — from arno0392 fork
    "A5-04-02": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        },
        "HUM": {
            "component": "sensor",
            "name": "Humidity",
            "device_class": "humidity",
            "unit_of_measurement": "%"
        }
    },
    "A5-04-03": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        },
        "HUM": {
            "component": "sensor",
            "name": "Humidity",
            "device_class": "humidity",
            "unit_of_measurement": "%"
        }
    },
    # 4BS Light Sensors (A5-06) — from arno0392 fork
    "A5-06-01": {
        "ILL": {
            "component": "sensor",
            "name": "Illuminance",
            "device_class": "illuminance",
            "unit_of_measurement": "lx"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    # 4BS Occupancy Sensors (A5-07) — from arno0392 fork
    "A5-07-02": {
        "PIR": {
            "component": "binary_sensor",
            "name": "Occupancy",
            "device_class": "occupancy"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    "A5-07-03": {
        "PIR": {
            "component": "binary_sensor",
            "name": "Occupancy",
            "device_class": "occupancy"
        },
        "ILL": {
            "component": "sensor",
            "name": "Illuminance",
            "device_class": "illuminance",
            "unit_of_measurement": "lx"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    # 4BS Light/Temp/Occupancy combos (A5-08) — from arno0392 fork
    "A5-08-01": {
        "ILL": {
            "component": "sensor",
            "name": "Illuminance",
            "device_class": "illuminance",
            "unit_of_measurement": "lx"
        },
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        },
        "PIR": {
            "component": "binary_sensor",
            "name": "Occupancy",
            "device_class": "occupancy"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    "A5-08-02": {
        "ILL": {
            "component": "sensor",
            "name": "Illuminance",
            "device_class": "illuminance",
            "unit_of_measurement": "lx"
        },
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        },
        "PIR": {
            "component": "binary_sensor",
            "name": "Occupancy",
            "device_class": "occupancy"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    "A5-08-03": {
        "ILL": {
            "component": "sensor",
            "name": "Illuminance",
            "device_class": "illuminance",
            "unit_of_measurement": "lx"
        },
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        },
        "PIR": {
            "component": "binary_sensor",
            "name": "Occupancy",
            "device_class": "occupancy"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    # 4BS Air Quality: CO2 / VOC (A5-09) — from arno0392 fork
    "A5-09-02": {
        "CO2": {
            "component": "sensor",
            "name": "CO2",
            "device_class": "carbon_dioxide",
            "unit_of_measurement": "ppm"
        },
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        }
    },
    "A5-09-04": {
        "CO2": {
            "component": "sensor",
            "name": "CO2",
            "device_class": "carbon_dioxide",
            "unit_of_measurement": "ppm"
        },
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        },
        "HUM": {
            "component": "sensor",
            "name": "Humidity",
            "device_class": "humidity",
            "unit_of_measurement": "%"
        }
    },
    "A5-09-05": {
        "VOC": {
            "component": "sensor",
            "name": "VOC",
            "device_class": "volatile_organic_compounds",
            "unit_of_measurement": "ppb"
        },
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        },
        "HUM": {
            "component": "sensor",
            "name": "Humidity",
            "device_class": "humidity",
            "unit_of_measurement": "%"
        }
    },
    # 4BS HVAC / Room Panels (A5-10) — from arno0392 fork
    "A5-10-01": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        },
        "SP": {
            "component": "sensor",
            "name": "Set Point",
            "icon": "mdi:thermometer-auto",
            "unit_of_measurement": "Â°C"
        },
        "FAN": {
            "component": "sensor",
            "name": "Fan Speed",
            "icon": "mdi:fan"
        }
    },
    "A5-10-06": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "Â°C"
        },
        "SP": {
            "component": "sensor",
            "name": "Set Point",
            "icon": "mdi:thermometer-auto",
            "unit_of_measurement": "Â°C"
        }
    },
    # 4BS Meters: electricity/gas/water (A5-12) — from arno0392 fork
    "A5-12-01": {
        "MR": {
            "component": "sensor",
            "name": "Energy",
            "device_class": "energy",
            "unit_of_measurement": "Wh",
            "state_class": "total_increasing"
        },
        "TMP": {
            "component": "sensor",
            "name": "Current Power",
            "device_class": "power",
            "unit_of_measurement": "W"
        }
    },
    "A5-12-02": {
        "MR": {
            "component": "sensor",
            "name": "Gas Volume",
            "unit_of_measurement": "mÂ³",
            "icon": "mdi:meter-gas",
            "state_class": "total_increasing"
        }
    },
    "A5-12-03": {
        "MR": {
            "component": "sensor",
            "name": "Water Volume",
            "unit_of_measurement": "L",
            "icon": "mdi:water",
            "state_class": "total_increasing"
        }
    },
    # 4BS Multi-sensors: vibration/window/lux (A5-14) — from arno0392 fork
    "A5-14-01": {
        "VIB": {
            "component": "binary_sensor",
            "name": "Vibration",
            "device_class": "vibration"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    "A5-14-05": {
        "OC": {
            "component": "binary_sensor",
            "name": "Contact",
            "device_class": "door"
        },
        "VIB": {
            "component": "binary_sensor",
            "name": "Vibration",
            "device_class": "vibration"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    "A5-14-09": {
        "OC": {
            "component": "binary_sensor",
            "name": "Contact",
            "device_class": "window"
        },
        "ILL": {
            "component": "sensor",
            "name": "Illuminance",
            "device_class": "illuminance",
            "unit_of_measurement": "lx"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    "A5-14-0A": {
        "OC": {
            "component": "binary_sensor",
            "name": "Contact",
            "device_class": "window"
        },
        "VIB": {
            "component": "binary_sensor",
            "name": "Vibration",
            "device_class": "vibration"
        },
        "ILL": {
            "component": "sensor",
            "name": "Illuminance",
            "device_class": "illuminance",
            "unit_of_measurement": "lx"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    # 4BS Digital Input (A5-30) — from arno0392 fork
    "A5-30-01": {
        "DI0": {
            "component": "binary_sensor",
            "name": "Input 0",
            "device_class": "power"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    "A5-30-02": {
        "DI0": {
            "component": "binary_sensor",
            "name": "Input 0",
            "device_class": "power"
        }
    },
    # VLD Electronic Switches and Dimmers (D2-01) — from arno0392 fork
    "D2-01-01": {
        "OV": {
            "component": "binary_sensor",
            "name": "Output",
            "device_class": "power",
            "payload_on": "100",
            "payload_off": "0",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-02": {
        "OV": {
            "component": "binary_sensor",
            "name": "Output",
            "device_class": "power",
            "payload_on": "100",
            "payload_off": "0",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-06": {
        "OV": {
            "component": "binary_sensor",
            "name": "Output",
            "device_class": "power",
            "payload_on": "100",
            "payload_off": "0",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-08": {
        "OV": {
            "component": "sensor",
            "name": "Brightness",
            "unit_of_measurement": "%",
            "icon": "mdi:brightness-6",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-09": {
        "OV": {
            "component": "sensor",
            "name": "Brightness",
            "unit_of_measurement": "%",
            "icon": "mdi:brightness-6",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-0A": {
        "OV": {
            "component": "sensor",
            "name": "Brightness",
            "unit_of_measurement": "%",
            "icon": "mdi:brightness-6",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-0B": {
        "OV": {
            "component": "sensor",
            "name": "Brightness",
            "unit_of_measurement": "%",
            "icon": "mdi:brightness-6",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-0C": {
        "OV": {
            "component": "sensor",
            "name": "Brightness",
            "unit_of_measurement": "%",
            "icon": "mdi:brightness-6",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-0D": {
        "OV": {
            "component": "binary_sensor",
            "name": "Output",
            "device_class": "power",
            "payload_on": "100",
            "payload_off": "0",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-0E": {
        "OV": {
            "component": "binary_sensor",
            "name": "Output",
            "device_class": "power",
            "payload_on": "100",
            "payload_off": "0",
            "value_template": "{{ value_json.OV }}"
        }
    },
    "D2-01-11": {
        "OV": {
            "component": "sensor",
            "name": "Channel 0 Brightness",
            "unit_of_measurement": "%",
            "icon": "mdi:brightness-6",
            "value_template": "{{ value_json.OV | string }}"
        },
        "OV_CH1": {
            "component": "sensor",
            "name": "Channel 1 Brightness",
            "unit_of_measurement": "%",
            "icon": "mdi:brightness-6",
            "value_template": "{{ value_json.OV_CH1 | string }}"
        }
    },
    "D2-01-12": {
        "OV": {
            "component": "binary_sensor",
            "name": "Channel 0",
            "device_class": "light",
            "payload_on": "100",
            "payload_off": "0",
            "value_template": "{{ value_json.OV | string }}"
        },
        "OV_CH1": {
            "component": "binary_sensor",
            "name": "Channel 1",
            "device_class": "light",
            "payload_on": "100",
            "payload_off": "0",
            "value_template": "{{ value_json.OV_CH1 | string }}"
        }
    },
    # VLD Blinds Control variants (D2-05) — from arno0392 fork
    "D2-05-01": {
        "POS": {
            "component": "cover",
            "name": "Position",
            "device_class": "blind"
        },
        "ANG": {
            "component": "sensor",
            "name": "Angle",
            "unit_of_measurement": "Â°"
        }
    },
    # RPS Rocker Switch, 4 Rockers (F6-03) — from arno0392 fork
    "F6-03-01": {
        "R1": {
            "component": "sensor",
            "name": "Rocker A",
            "icon": "mdi:gesture-tap-button",
            "value_template": "{{ value_json.R1_text }}"
        },
        "R2": {
            "component": "sensor",
            "name": "Rocker B",
            "icon": "mdi:gesture-tap-button",
            "value_template": "{{ value_json.R2_text }}"
        },
        "EB": {
            "component": "binary_sensor",
            "name": "Energy Bow",
            "device_class": "power"
        }
    },
    "F6-03-02": {
        "R1": {
            "component": "sensor",
            "name": "Rocker A",
            "icon": "mdi:gesture-tap-button",
            "value_template": "{{ value_json.R1_text }}"
        },
        "R2": {
            "component": "sensor",
            "name": "Rocker B",
            "icon": "mdi:gesture-tap-button",
            "value_template": "{{ value_json.R2_text }}"
        },
        "EB": {
            "component": "binary_sensor",
            "name": "Energy Bow",
            "device_class": "power"
        }
    },
    # RPS Window Handle (F6-10) — from arno0392 fork
    "F6-10-00": {
        "WIN": {
            "component": "sensor",
            "name": "Window Handle",
            "icon": "mdi:window-open",
            "value_template": "{{ value_json.WIN_text }}"
        }
    },
}

def _normalize_address(address: str) -> str:
    """Normalize address to 8-char lowercase hex without 0x prefix.
    e.g., '0x05834FA4' -> '05834fa4'
    Lowercase to match ChristopheHD/Slim addon identifier format.
    """
    addr = address.strip().lower()
    if addr.startswith("0x"):
        addr = addr[2:]
    return addr.zfill(8)


def _normalize_eep(eep_id: str) -> str:
    """Normalize EEP to 6-char lowercase format without dashes.
    e.g., 'A5-30-03' -> 'a53003'
    """
    return eep_id.lower().replace("-", "")


class MappingManager:
    """Manages EEP to MQTT/HA entity mappings"""

    def __init__(self, config_path: str, eep_manager=None):
        self.config_path = config_path
        self.eep_manager = eep_manager
        self.mappings_file = os.path.join(config_path, "mapping.yaml")
        self.custom_mappings: Dict[str, Dict[str, Any]] = {}

    async def initialize(self):
        """Initialize mapping manager - load custom mappings"""
        await self._load_custom_mappings()
        logger.info(f"Mapping Manager initialized with {len(self.custom_mappings)} custom mappings")

    async def _load_custom_mappings(self):
        """Load custom mappings from file"""
        if not os.path.exists(self.mappings_file):
            return

        try:
            async with aiofiles.open(self.mappings_file, 'r') as f:
                content = await f.read()
                data = yaml.safe_load(content)
                if data and isinstance(data, dict):
                    self.custom_mappings = data
                    logger.info(f"Loaded {len(self.custom_mappings)} custom mappings")
        except Exception as e:
            logger.error(f"Failed to load custom mappings: {e}")

    async def save_mappings(self):
        """Save custom mappings to file"""
        try:
            os.makedirs(self.config_path, exist_ok=True)
            async with aiofiles.open(self.mappings_file, 'w') as f:
                await f.write(yaml.dump(
                    self.custom_mappings,
                    default_flow_style=False,
                    allow_unicode=True
                ))
            logger.info("Saved custom mappings")
        except Exception as e:
            logger.error(f"Failed to save mappings: {e}")

    def get_mapping(self, eep_id: str) -> Dict[str, Any]:
        """Get mapping for a device

        Priority:
        1. Custom EEP profile ha_mapping (from custom_eep YAML)
        2. Mapping overrides (from inline mapping editor)
        3. Custom EEP mapping (from mapping.yaml)
        4. Default EEP mapping
        5. Empty dict
        """
        eep_id = eep_id.upper()

        # 1. Check custom EEP profile ha_mapping
        if self.eep_manager:
            profile = self.eep_manager.get_profile(eep_id)
            if profile and profile.ha_mapping:
                logger.debug(f"Using ha_mapping from custom EEP profile {eep_id}")
                return profile.ha_mapping

        # 2. Check mapping overrides (from inline editor, cached in memory)
        if self.eep_manager:
            override = self.eep_manager.get_mapping_override_sync(eep_id)
            if override:
                logger.debug(f"Using mapping override for {eep_id}")
                return override

        # 3. Custom mappings from mapping.yaml
        if eep_id in self.custom_mappings:
            return self.custom_mappings[eep_id]

        # 4. Default mappings
        if eep_id in DEFAULT_MAPPINGS:
            return DEFAULT_MAPPINGS[eep_id]

        return {}

    async def set_mapping(self, eep_id: str, mapping: Dict[str, Any]):
        """Set custom mapping for an EEP profile"""
        eep_id = eep_id.upper()
        self.custom_mappings[eep_id] = mapping
        await self.save_mappings()
        logger.info(f"Set mapping for {eep_id}")

    async def delete_mapping(self, eep_id: str) -> bool:
        """Delete custom mapping for an EEP profile"""
        eep_id = eep_id.upper()
        if eep_id in self.custom_mappings:
            del self.custom_mappings[eep_id]
            await self.save_mappings()
            logger.info(f"Deleted mapping for {eep_id}")
            return True
        return False

    def get_all_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Get all mappings (merged default + custom)"""
        result = dict(DEFAULT_MAPPINGS)
        result.update(self.custom_mappings)
        return result

    def build_unique_id(self, eep_id: str, address: str, sender: str, shortcut: str) -> str:
        """Build ChristopheHD-compatible unique ID for HA discovery.

        Format: enocean_{EEP6}_{ADDR8}_{SHORTCUT}
        With sender: enocean_{EEP6}_{ADDR8}_{SENDER8}_{SHORTCUT}
        """
        eep = _normalize_eep(eep_id)
        addr = _normalize_address(address)

        if sender:
            sndr = _normalize_address(sender)
            return f"enocean_{eep}_{addr}_{sndr}_{shortcut}"
        else:
            return f"enocean_{eep}_{addr}_{shortcut}"

    def get_ha_discovery_configs(
        self,
        device_name: str,
        eep_id: str,
        device_address: str,
        device_sender: str,
        mqtt_prefix: str,
        device_info: Dict[str, Any],
        actuator_type: str = "",
        invert: bool = False
    ) -> List[Dict[str, Any]]:
        """Generate Home Assistant MQTT discovery configurations.

        Returns a list of discovery configs for all entities defined in the mapping.
        Uses ChristopheHD-compatible UID format and per-device availability.

        If actuator_type is set (light/switch/cover), generates a controllable entity
        instead of sensor entities from the EEP profile.
        """
        configs = []

        avail_config = {
            "topic": f"{mqtt_prefix}/{device_name}/availability",
            "payload_available": "online",
            "payload_not_available": "offline"
        }

        # Actuator mode: create a controllable entity (light/switch/cover)
        if actuator_type in ("light", "switch", "cover"):
            unique_id = self.build_unique_id(eep_id, device_address, device_sender, actuator_type)

            if actuator_type == "light":
                config = {
                    "name": None,  # Use device name
                    "unique_id": unique_id,
                    "object_id": f"{device_name}".lower().replace(" ", "_"),
                    "command_topic": f"{mqtt_prefix}/{device_name}/set",
                    "state_topic": f"{mqtt_prefix}/{device_name}/state",
                    "state_value_template": "{{ value_json.state }}",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    # Brightness support for dimmers (A5-38-08)
                    "brightness_command_topic": f"{mqtt_prefix}/{device_name}/set",
                    "brightness_state_topic": f"{mqtt_prefix}/{device_name}/state",
                    "brightness_value_template": "{{ value_json.brightness }}",
                    "brightness_scale": 100,
                    "on_command_type": "brightness",
                    "optimistic": False,
                    "icon": "mdi:lightbulb",
                    "device": device_info,
                    "availability": avail_config
                }
            elif actuator_type == "switch":
                config = {
                    "name": None,
                    "unique_id": unique_id,
                    "object_id": f"{device_name}".lower().replace(" ", "_"),
                    "command_topic": f"{mqtt_prefix}/{device_name}/set",
                    "state_topic": f"{mqtt_prefix}/{device_name}/state",
                    "value_template": "{{ value_json.state }}",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "optimistic": True,
                    "icon": "mdi:power",
                    "device": device_info,
                    "availability": avail_config
                }
            elif actuator_type == "cover":
                config = {
                    "name": None,
                    "unique_id": unique_id,
                    "object_id": f"{device_name}".lower().replace(" ", "_"),
                    "command_topic": f"{mqtt_prefix}/{device_name}/set",
                    "state_topic": f"{mqtt_prefix}/{device_name}/state",
                    "value_template": "{{ value_json.state }}",
                    "device_class": "blind",
                    "optimistic": True,
                    "icon": "mdi:blinds",
                    "device": device_info,
                    "availability": avail_config
                }

                # D2-05-xx blind actuators (e.g. NodOn) support a real position
                # command. Add a position slider driven via {device}/set/position
                # (fits the existing {prefix}/+/set/# subscription). Position is
                # reported back as POS if the actuator replies. Normally EnOcean
                # 0 % = open, HA 100 = open, so POS is inverted here; `invert`
                # (reverse-wired shutter) keeps POS as-is. This must match the
                # command-side inversion in send_d2_05_command.
                if eep_id.upper().startswith("D2-05"):
                    config["set_position_topic"] = f"{mqtt_prefix}/{device_name}/set/position"
                    config["position_topic"] = f"{mqtt_prefix}/{device_name}/state"
                    pos_expr = "value_json.POS" if invert else "(100 - value_json.POS)"
                    config["position_template"] = (
                        f"{{{{ {pos_expr} if value_json.POS is defined else none }}}}"
                    )
                    config["position_open"] = 100
                    config["position_closed"] = 0

            configs.append({
                "component": actuator_type,
                "unique_id": unique_id,
                "config": config
            })

            # Return early — actuators don't need sensor entities from EEP profile
            # Still add diagnostic entities below
        else:
            # Sensor mode: create entities from EEP mapping
            mapping = self.get_mapping(eep_id)

            for field_name, field_config in mapping.items():
                component = field_config.get("component", "sensor")

                # Build unique ID (ChristopheHD compatible)
                unique_id = self.build_unique_id(eep_id, device_address, device_sender, field_name)

                # Build discovery config
                config = {
                    "name": field_config.get("name", field_name),
                    "unique_id": unique_id,
                    "object_id": f"{device_name}_{field_name}".lower().replace(" ", "_"),
                    "state_topic": f"{mqtt_prefix}/{device_name}/state",
                    "value_template": field_config.get(
                        "value_template",
                        f"{{{{ value_json.{field_name} }}}}"
                    )
                }

                # Pass through all mapping fields to discovery config
                # Internal keys are already handled above or are not HA discovery fields
                _INTERNAL_KEYS = {"component", "name", "value_template"}
                for key, value in field_config.items():
                    if key not in _INTERNAL_KEYS and key not in config:
                        config[key] = value

                # Binary sensor: HA expects "ON"/"OFF" by default, but EEP values are 0/1
                if component == "binary_sensor":
                    config["payload_on"] = "1"
                    config["payload_off"] = "0"

                # Add device info
                config["device"] = device_info

                # Add command topic for controllable entities
                if component in ["switch", "light", "cover", "climate", "fan"]:
                    config["command_topic"] = f"{mqtt_prefix}/{device_name}/set"

                    if component == "cover":
                        config["position_topic"] = f"{mqtt_prefix}/{device_name}/state"
                        config["position_template"] = f"{{{{ value_json.{field_name} }}}}"
                        config["set_position_topic"] = f"{mqtt_prefix}/{device_name}/position/set"

                # Per-device availability (not global gateway status)
                config["availability"] = avail_config

                configs.append({
                    "component": component,
                    "unique_id": unique_id,
                    "config": config
                })

        # Auto-add diagnostic entities for every device: RSSI + Last Seen
        state_topic = f"{mqtt_prefix}/{device_name}/state"

        # RSSI sensor
        rssi_uid = self.build_unique_id(eep_id, device_address, device_sender, "rssi")
        configs.append({
            "component": "sensor",
            "unique_id": rssi_uid,
            "config": {
                "name": "RSSI",
                "unique_id": rssi_uid,
                "object_id": f"{device_name}_rssi".lower().replace(" ", "_"),
                "state_topic": state_topic,
                "value_template": "{{ value_json.rssi }}",
                "device_class": "signal_strength",
                "unit_of_measurement": "dBm",
                "icon": "mdi:wifi",
                "entity_category": "diagnostic",
                "device": device_info,
                "availability": avail_config
            }
        })

        # Last Seen sensor
        last_seen_uid = self.build_unique_id(eep_id, device_address, device_sender, "last_seen")
        configs.append({
            "component": "sensor",
            "unique_id": last_seen_uid,
            "config": {
                "name": "Last Seen",
                "unique_id": last_seen_uid,
                "object_id": f"{device_name}_last_seen".lower().replace(" ", "_"),
                "state_topic": state_topic,
                "value_template": "{{ value_json.last_seen }}",
                "device_class": "timestamp",
                "icon": "mdi:clock-outline",
                "entity_category": "diagnostic",
                "device": device_info,
                "availability": avail_config
            }
        })

        return configs

    def build_device_info(self, device) -> Dict[str, Any]:
        """Build HA device info from device object"""
        addr = _normalize_address(device.address)
        return {
            "identifiers": [f"enocean_{addr}"],
            "name": device.description or device.name,
            "manufacturer": device.manufacturer or "EnOcean",
            "model": device.eep_id,
        }
