"""
Telegram Buffer - Stores recent EnOcean telegrams for debugging
"""

import logging
from typing import List, Dict, Any, Optional
from collections import deque
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TelegramEntry:
    """A stored telegram entry"""
    timestamp: str
    sender_id: str
    rorg: str
    data: str
    status: int
    dbm: int
    device_name: Optional[str] = None
    eep_id: Optional[str] = None
    decoded: Optional[Dict[str, Any]] = None
    is_teach_in: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TelegramBuffer:
    """Ring buffer for storing recent telegrams"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)
        self._unknown_devices: deque = deque(maxlen=50)

    def add(
        self,
        sender_id: str,
        rorg: str,
        data: str,
        status: int,
        dbm: int,
        device_name: Optional[str] = None,
        eep_id: Optional[str] = None,
        decoded: Optional[Dict[str, Any]] = None,
        is_teach_in: bool = False
    ):
        """Add a telegram to the buffer"""
        entry = TelegramEntry(
            timestamp=datetime.now().isoformat(),
            sender_id=sender_id,
            rorg=rorg,
            data=data,
            status=status,
            dbm=dbm,
            device_name=device_name,
            eep_id=eep_id,
            decoded=decoded,
            is_teach_in=is_teach_in
        )
        self._buffer.append(entry)

        # Track unknown devices separately
        if device_name is None:
            self._add_unknown_device(sender_id, rorg, dbm)

    def _add_unknown_device(self, sender_id: str, rorg: str, dbm: int):
        """Track unknown devices for easy discovery"""
        # Check if already in list
        for item in self._unknown_devices:
            if item["sender_id"] == sender_id:
                item["last_seen"] = datetime.now().isoformat()
                item["count"] = item.get("count", 0) + 1
                item["dbm"] = dbm
                return

        self._unknown_devices.append({
            "sender_id": sender_id,
            "rorg": rorg,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "count": 1,
            "dbm": dbm
        })

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most recent telegrams"""
        entries = list(self._buffer)[-limit:]
        return [e.to_dict() for e in reversed(entries)]

    def get_by_device(self, device_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent telegrams for a specific device"""
        entries = [e for e in self._buffer if e.device_name == device_name]
        return [e.to_dict() for e in entries[-limit:]]

    def get_by_sender(self, sender_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent telegrams from a specific sender"""
        sender_id = sender_id.upper()
        entries = [e for e in self._buffer if e.sender_id.upper() == sender_id]
        return [e.to_dict() for e in entries[-limit:]]

    def get_unknown_devices(self) -> List[Dict[str, Any]]:
        """Get list of unknown devices that have sent telegrams"""
        return list(self._unknown_devices)

    def get_teach_ins(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent teach-in telegrams"""
        entries = [e for e in self._buffer if e.is_teach_in]
        return [e.to_dict() for e in entries[-limit:]]

    def clear(self):
        """Clear the buffer"""
        self._buffer.clear()
        self._unknown_devices.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        return {
            "total_count": len(self._buffer),
            "max_size": self.max_size,
            "unknown_device_count": len(self._unknown_devices),
            "teach_in_count": sum(1 for e in self._buffer if e.is_teach_in)
        }
