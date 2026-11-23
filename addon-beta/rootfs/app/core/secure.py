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

Sending (ADR-0056): the app generates a key, hands it to the device with its
own secure teach-in, and from then on encapsulates (0x31) every telegram
addressed to that device. The sending rolling code is saved before the
telegram goes out, so it is never used twice. No pre-shared key in either
direction. Keys stay in /data/secure_devices.yaml and are never
logged. Backups and exports carry the file, so a restored secure device
works without a new teach-in; treat a backup as secret.

AES-128 is implemented here (encryption only, all VAES and CMAC need) rather
than adding a native dependency to the image; tests check it against the
FIPS-197 and RFC 4493 vectors.
"""

import logging
import os
import secrets
from typing import Any, Dict, List, Optional, Tuple

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
    """VAES; encryption and decryption are the same operation. From the second
    16-byte block on, the previous key stream is mixed into the input."""
    iv = bytes(a ^ b for a, b in zip(PUBLIC_KEY, rlc.ljust(16, b"\x00")))
    out, pad = b"", bytes(16)
    for i in range(0, len(data), 16):
        pad = aes128_encrypt(key, bytes(a ^ b for a, b in zip(iv, pad)))
        out += bytes(a ^ b for a, b in zip(data[i:i + 16], pad))
    return out


# --- teach-in and decryption --------------------------------------------------

# A secure PTM 210/215 (teach-in type "switch") sends no RPS byte: its
# decrypted data is the D2-03-00 code in the low nibble, as FHEM's
# switch.00 decodes it. Translated to the F6-02 byte and status the
# configured rocker profile expects (R1 7-5, EB 4, R2 3-1, SA 0; T21 0x20,
# NU 0x10). Button numbers: AI 0, A0 1, BI 2, B0 3. Issue #62.
_PTM_RPS = {
    14: (0x30, 0x30),  # A0
    13: (0x10, 0x30),  # AI
    12: (0x70, 0x30),  # B0
    11: (0x50, 0x30),  # BI
    7: (0x37, 0x30),   # A0 + B0
    10: (0x35, 0x30),  # A0 + BI
    5: (0x17, 0x30),   # AI + B0
    9: (0x15, 0x30),   # AI + BI
    8: (0x10, 0x20),   # energy bow pressed, no button
    6: (0x70, 0x20),   # 3 or 4 buttons
    15: (0x00, 0x20),  # released
}


def ptm_to_rps(plain: bytes) -> Optional[Tuple[int, int]]:
    """(F6 data byte, status) for the decrypted data of a secure PTM switch,
    or None when it is not a known code."""
    if not plain:
        return None
    return _PTM_RPS.get(plain[0] & 0x0F)


def parse_slf(slf: int) -> Dict[str, Any]:
    return {
        "rlc_len": {0: 0, 1: 2, 2: 3, 3: 4}[(slf >> 6) & 0x03],
        "rlc_tx": bool(slf & 0x20),
        "mac_len": {0: 0, 1: 3, 2: 4, 3: 0}[(slf >> 3) & 0x03],
        "data_enc": slf & 0x07,  # 3 = VAES
    }


def _addr(address: str) -> str:
    return "0x" + str(address).upper().replace("0X", "")


SEND_SLF = 0x8B  # RLC 3 bytes not sent, CMAC 3 bytes, VAES
# How the 16 key bytes are split over the teach-in telegrams: the layout of
# the specification's example, and the one of gateways that address theirs.
_KEY_SPLIT = {2: (7, 9), 3: (4, 8, 4)}
# RORG + data of an addressed ERP1 telegram
MAX_ADDRESSED = 10
# Already secure, teach-in or remote management telegrams stay as they are
_NEVER_ENCRYPT = {RORG_SEC, RORG_SEC_ENCAPS, RORG_SEC_TI, 0xC5, 0xC6, 0xC7, 0xD4, 0xF6}


class SecureSendError(Exception):
    pass


def build_teach_in(key: bytes, rlc: bytes, parts: int, bidirectional: bool = False) -> List[bytes]:
    """Data fields of the app's own secure teach-in (0x35)."""
    out, off = [], 0
    for idx, n in enumerate(_KEY_SPLIT[parts]):
        head = (bytes([(parts << 4) | (0x01 if bidirectional else 0), SEND_SLF]) + rlc) if idx == 0 else bytes([idx << 6])
        out.append(head + key[off:off + n])
        off += n
    return out


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

    def _save(self) -> bool:
        try:
            tmp = self._file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                yaml.safe_dump(self._devices, f)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self._file)
            return True
        except Exception as e:
            logger.error(f"Could not write {self._file}: {e}")
            return False

    # --- sending --------------------------------------------------------------

    def sends_secure(self, address: str) -> bool:
        return bool((self._devices.get(_addr(address)) or {}).get("snd_key"))

    def start_sending(self, address: str, parts: int) -> List[bytes]:
        """New key for this device; returns the teach-in telegrams. The device
        uses the same key for its own telegrams unless it sends a teach-in of
        its own, which then replaces the receiving key."""
        address, key, rlc = _addr(address), secrets.token_bytes(16), bytes(3)
        previous = self._devices.get(address)
        entry = dict(parse_slf(SEND_SLF), key=key.hex(), rlc=rlc.hex(),
                     switch=False, bidirectional=True, snd_key=key.hex(), snd_rlc=rlc.hex(), rx_seen=False)
        if previous:
            # Whether the device took the new key shows only when it uses it.
            # Until then its old one is accepted as well.
            entry["old"] = previous.get("old") or dict(previous)
        self._devices[address] = entry
        if not self._save():
            self._restore_entry(address, previous)
            raise SecureSendError("the key could not be saved")
        return build_teach_in(key, rlc, parts, bidirectional=True)

    def _restore_entry(self, address: str, entry):
        if entry is None:
            self._devices.pop(address, None)
        else:
            self._devices[address] = entry

    def stop_sending(self, address: str):
        entry = self._devices.get(_addr(address))
        if entry:
            if "old" in entry:
                # it never used the new key: back to what it had
                entry = entry["old"]
                self._devices[_addr(address)] = entry
            entry.pop("snd_key", None)
            entry.pop("snd_rlc", None)
            if not entry.get("rx_seen", True):
                del self._devices[_addr(address)]
            self._save()

    def encrypt(self, address: str, rorg: int, payload: bytes) -> Tuple[int, bytes]:
        """(0x31, data) for one telegram to the device. The next rolling code
        is saved first; without that nothing is sent."""
        address = _addr(address)
        dev = self._devices[address]
        key, rlc = bytes.fromhex(dev["snd_key"]), bytes.fromhex(dev["snd_rlc"])
        plain = bytes([rorg]) + payload
        if 1 + len(plain) + 3 > MAX_ADDRESSED:
            raise SecureSendError(f"{len(payload)} data bytes do not fit into one secure telegram")
        dev["snd_rlc"] = ((int.from_bytes(rlc, "big") + 1) % (1 << 24)).to_bytes(3, "big").hex()
        if not self._save():
            dev["snd_rlc"] = rlc.hex()
            raise SecureSendError("the rolling code could not be saved")
        enc = vaes(key, rlc, plain)
        return RORG_SEC_ENCAPS, enc + aes_cmac(key, bytes([RORG_SEC_ENCAPS]) + enc + rlc)[:3]

    def must_encrypt(self, address: str, rorg: int) -> bool:
        return rorg not in _NEVER_ENCRYPT and self.sends_secure(address)

    @property
    def file(self) -> str:
        return self._file

    def restore(self, data: Dict[str, Dict[str, Any]], configured: List[str]) -> int:
        """Take keys from a backup. A key the app already has for an address
        wins: it is the one the device uses now, with the newer rolling code
        (a restored older RLC could fall outside the window). Keys of
        addresses that are not configured afterwards are dropped. Returns the
        number of keys taken from the backup."""
        taken = 0
        for address, entry in (data or {}).items():
            address = _addr(address)
            if address in self._devices or not isinstance(entry, dict) or len(str(entry.get("key", ""))) != 32:
                continue
            self._devices[address] = entry
            taken += 1
        self.prune(configured)
        self._save()
        return taken

    def prune(self, configured: List[str]):
        keep = {_addr(a) for a in configured}
        gone = [a for a in self._devices if a not in keep]
        for address in gone:
            del self._devices[address]
        if gone:
            self._save()

    def is_switch(self, address: str) -> bool:
        """Taught in as a PTM switch (teach-in TYPE bit)."""
        return bool((self._devices.get(_addr(address)) or {}).get("switch"))

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
                self._pending.pop(address, None)
                return self._store(address, entry)
            # two telegrams, or three (some gateways address theirs)
            self._pending[address] = (cnt, 1, entry)
            return None
        if address in self._pending:
            cnt, expected, entry = self._pending[address]
            if idx == expected:
                entry["key"] += data[1:].hex()
                if idx + 1 < cnt:
                    self._pending[address] = (cnt, idx + 1, entry)
                    return None
                del self._pending[address]
                return self._store(address, entry)
            if idx < expected:
                return None  # a repeated telegram
            del self._pending[address]
        logger.warning(f"Secure teach-in from {address}: telegram {idx} of {cnt} out of sequence")
        return None

    def _store(self, address: str, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if len(entry["key"]) != 32:
            logger.warning(f"Secure teach-in from {address}: key has {len(entry['key']) // 2} bytes, expected 16")
            return None
        old = self._devices.get(address) or {}
        for field in ("snd_key", "snd_rlc"):  # the app's own key stays
            if field in old:
                entry[field] = old[field]
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
        plain = self._decrypt_with(dev, rorg, payload)
        if plain is not None:
            dev.pop("old", None)
            dev["rx_seen"] = True
        elif "old" in dev:
            plain = self._decrypt_with(dev["old"], rorg, payload)
        if plain is None:
            logger.warning(f"Secure telegram from {address} could not be verified (wrong key or RLC out of window)")
            return None
        self._save()
        if rorg == RORG_SEC_ENCAPS:
            return plain[0], plain[1:]
        return None, plain

    @staticmethod
    def _decrypt_with(dev: Dict[str, Any], rorg: int, payload: bytes) -> Optional[bytes]:
        """The decrypted data, with dev's rolling code moved on, or None."""
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
            return plain
        return None
