"""
Secure EnOcean telegrams: secure teach-in (RORG 0x35), VAES decryption and
AES-CMAC check of secure data (RORG 0x30 and 0x31). Issue #62, ADR-0046.

As in the EnOcean Security Specification, cross-checked against FHEM
10_EnOcean.pm (EnOcean_sec_*):

- teach-in, two telegrams: TEACH_IN_INFO (IDX, CNT, PSK, TYPE, INFO), SLF
  (RLC_ALGO, RLC_TX, MAC_ALGO, DATA_ENC), then RLC and the first part of the
  16-byte key; the second telegram carries the rest of the key
- data: encrypted data, the RLC if RLC_TX, then a 3 or 4 byte CMAC
- CMAC (RFC 4493, truncated) over RORG + encrypted data + RLC
- VAES: data XOR AES128(key, PUBLIC_KEY XOR RLC), the RLC left-aligned in 16
  bytes
- the receiver keeps the RLC and tries the next 128 values when it is not
  sent, so a few lost telegrams do not lock the device out
- 0x31 (encapsulated): the first decrypted byte is the inner RORG. 0x30 has
  none; its data is decoded with the device's configured profile.

Only receiving is supported, without a pre-shared key: the teach-in of a
device that encrypts it with a PSK is refused, and the app never sends
secure telegrams. Keys stay in /data/secure_devices.yaml and are never
logged.

AES-128 is implemented here (encryption only, all VAES and CMAC need) rather
than adding a native dependency to the image; tests check it against the
FIPS-197 and RFC 4493 vectors.
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

RORG_SEC = 0x30
RORG_SEC_ENCAPS = 0x31
RORG_SEC_TI = 0x35
PUBLIC_KEY = bytes.fromhex("3410de8f1aba3eff9f5a117172eacabd")
RLC_WINDOW = 128

# --- AES-128, encryption only ------------------------------------------------

_SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16")
_RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _xtime(a: int) -> int:
    a <<= 1
    return (a ^ 0x1B) & 0xFF if a & 0x100 else a


def _expand_key(key: bytes):
    words = [list(key[i:i + 4]) for i in range(0, 16, 4)]
    for i in range(4, 44):
        t = list(words[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]
            t = [_SBOX[b] for b in t]
            t[0] ^= _RCON[i // 4 - 1]
        words.append([a ^ b for a, b in zip(words[i - 4], t)])
    return [sum(words[r * 4:r * 4 + 4], []) for r in range(11)]


def aes128_encrypt(key: bytes, block: bytes) -> bytes:
    rk = _expand_key(key)
    s = [b ^ k for b, k in zip(block, rk[0])]
    for rnd in range(1, 11):
        s = [_SBOX[b] for b in s]
        # ShiftRows, state is column-major
        s = [s[(c * 4 + r + 4 * r) % 16] for c in range(4) for r in range(4)]
        if rnd != 10:
            m = []
            for c in range(4):
                a = s[c * 4:c * 4 + 4]
                x = a[0] ^ a[1] ^ a[2] ^ a[3]
                m += [a[i] ^ x ^ _xtime(a[i] ^ a[(i + 1) % 4]) for i in range(4)]
            s = m
        s = [b ^ k for b, k in zip(s, rk[rnd])]
    return bytes(s)


def _shift_left(b: bytes) -> bytes:
    v = (int.from_bytes(b, "big") << 1) & ((1 << 128) - 1)
    return v.to_bytes(16, "big")


def aes_cmac(key: bytes, msg: bytes) -> bytes:
    """RFC 4493."""
    l = aes128_encrypt(key, bytes(16))
    k1 = _shift_left(l)
    if l[0] & 0x80:
        k1 = k1[:-1] + bytes([k1[-1] ^ 0x87])
    k2 = _shift_left(k1)
    if k1[0] & 0x80:
        k2 = k2[:-1] + bytes([k2[-1] ^ 0x87])
    n = max(1, (len(msg) + 15) // 16)
    complete = len(msg) > 0 and len(msg) % 16 == 0
    last = msg[(n - 1) * 16:]
    if complete:
        last = bytes(a ^ b for a, b in zip(last, k1))
    else:
        last = last + b"\x80" + bytes(15 - len(last))
        last = bytes(a ^ b for a, b in zip(last, k2))
    x = bytes(16)
    for i in range(n - 1):
        x = aes128_encrypt(key, bytes(a ^ b for a, b in zip(x, msg[i * 16:(i + 1) * 16])))
    return aes128_encrypt(key, bytes(a ^ b for a, b in zip(x, last)))


def vaes(key: bytes, rlc: bytes, data: bytes) -> bytes:
    """VAES for up to 16 bytes (an ERP1 telegram never carries more)."""
    aes_in = bytes(a ^ b for a, b in zip(PUBLIC_KEY, rlc.ljust(16, b"\x00")))
    pad = aes128_encrypt(key, aes_in)
    return bytes(a ^ b for a, b in zip(data, pad))


# --- teach-in and decryption --------------------------------------------------

def parse_slf(slf: int) -> Dict[str, Any]:
    return {
        "rlc_len": {0: 0, 1: 2, 2: 3, 3: 4}[(slf >> 6) & 0x03],
        "rlc_tx": bool(slf & 0x20),
        "mac_len": {0: 0, 1: 3, 2: 4, 3: 0}[(slf >> 3) & 0x03],
        "data_enc": slf & 0x07,  # 3 = VAES
    }


def _addr(address: str) -> str:
    return "0x" + str(address).upper().replace("0X", "")


class SecureDevices:
    """Keys and rolling codes per sender address."""

    def __init__(self, config_path: str):
        self._file = os.path.join(config_path, "secure_devices.yaml")
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._pending: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(self._file):
            try:
                with open(self._file, encoding="utf-8") as f:
                    self._devices = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Could not read {self._file}: {e}")

    def _save(self):
        try:
            tmp = self._file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                yaml.safe_dump(self._devices, f)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self._file)
        except Exception as e:
            logger.error(f"Could not write {self._file}: {e}")

    def known(self, address: str) -> bool:
        return _addr(address) in self._devices

    def forget(self, address: str):
        if self._devices.pop(_addr(address), None) is not None:
            self._save()

    def teach_in(self, address: str, data: bytes) -> Optional[Dict[str, Any]]:
        """Feed one 0x35 telegram. Returns the device's security settings
        once both parts arrived, otherwise None."""
        address = _addr(address)
        if len(data) < 2:
            return None
        info = data[0]
        idx, cnt = (info >> 6) & 0x03, (info >> 4) & 0x03
        psk, ti_type, ti_info = bool(info & 0x08), (info >> 2) & 0x01, info & 0x03
        if idx == 0:
            slf = parse_slf(data[1])
            if psk:
                logger.warning(f"Secure teach-in from {address}: encrypted with a pre-shared key, not supported")
                return None
            if slf["data_enc"] != 3 or slf["mac_len"] == 0 or slf["rlc_len"] == 0:
                logger.warning(f"Secure teach-in from {address}: unsupported security level "
                               f"(SLF 0x{data[1]:02X}); only VAES with RLC and CMAC is supported")
                return None
            n = slf["rlc_len"]
            entry = dict(slf, rlc=data[2:2 + n].hex(), key=data[2 + n:].hex(),
                         switch=bool(ti_type), bidirectional=bool(ti_info and not ti_type))
            if cnt <= 1:
                return self._store(address, entry)
            self._pending[address] = entry
            return None
        if idx == 1 and address in self._pending:
            entry = self._pending.pop(address)
            entry["key"] += data[1:].hex()
            return self._store(address, entry)
        logger.warning(f"Secure teach-in from {address}: telegram {idx} of {cnt} out of sequence")
        return None

    def _store(self, address: str, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if len(entry["key"]) != 32:
            logger.warning(f"Secure teach-in from {address}: key has {len(entry['key']) // 2} bytes, expected 16")
            return None
        self._devices[address] = entry
        self._save()
        logger.info(f"Secure teach-in from {address}: stored (RLC {entry['rlc_len']} bytes, "
                    f"CMAC {entry['mac_len']} bytes{', switch' if entry.get('switch') else ''})")
        return {k: v for k, v in entry.items() if k != "key"}

    def decrypt(self, address: str, rorg: int, payload: bytes) -> Optional[Tuple[Optional[int], bytes]]:
        """(inner RORG or None for 0x30, plain data), or None if the
        telegram cannot be verified."""
        address = _addr(address)
        dev = self._devices.get(address)
        if dev is None:
            return None
        key = bytes.fromhex(dev["key"])
        n_rlc, n_mac = dev["rlc_len"], dev["mac_len"]
        tail = n_mac + (n_rlc if dev["rlc_tx"] else 0)
        if len(payload) <= tail:
            return None
        enc = payload[:len(payload) - tail]
        mac = payload[len(payload) - n_mac:]
        stored = int(dev["rlc"], 16)
        limit = 1 << (8 * n_rlc)
        if dev["rlc_tx"]:
            candidates = [int.from_bytes(payload[len(enc):len(enc) + n_rlc], "big")]
        else:
            candidates = [(stored + i) % limit for i in range(RLC_WINDOW + 1)]
        for value in candidates:
            if dev["rlc_tx"] and (value - stored) % limit > (limit // 2):
                break  # an old RLC: a replayed telegram
            rlc = value.to_bytes(n_rlc, "big")
            if aes_cmac(key, bytes([rorg]) + enc + rlc)[:n_mac] != mac:
                continue
            plain = vaes(key, rlc, enc)
            dev["rlc"] = ((value + 1) % limit).to_bytes(n_rlc, "big").hex()
            self._save()
            if rorg == RORG_SEC_ENCAPS:
                return plain[0], plain[1:]
            return None, plain
        logger.warning(f"Secure telegram from {address} could not be verified (wrong key or RLC out of window)")
        return None
