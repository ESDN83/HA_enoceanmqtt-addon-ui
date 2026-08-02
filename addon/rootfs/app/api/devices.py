"""
Devices API - CRUD operations for EnOcean devices
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter()


class DeviceCreate(BaseModel):
    """Device creation model"""
    name: str
    address: str
    rorg: str
    func: str
    type: str
    sender_id: Optional[str] = ""
    description: Optional[str] = ""
    room: Optional[str] = ""
    manufacturer: Optional[str] = ""
    actuator_type: Optional[str] = ""  # "light", "switch", "cover", or ""
    invert: Optional[bool] = False  # cover: reverse Open/Close + position
    channel: Optional[int] = 0  # multi-channel actuators (D2-01-11/12): 0 or 1


class DeviceUpdate(BaseModel):
    """Device update model"""
    name: Optional[str] = None  # rename: the name is the primary key + MQTT topic base
    address: Optional[str] = None
    rorg: Optional[str] = None
    func: Optional[str] = None
    type: Optional[str] = None
    sender_id: Optional[str] = None
    description: Optional[str] = None
    room: Optional[str] = None
    manufacturer: Optional[str] = None
    actuator_type: Optional[str] = None
    invert: Optional[bool] = None
    channel: Optional[int] = None


# A device name is three things at once: the primary key, the base of its MQTT
# topics, and a URL path segment. '/', '+' and '#' are illegal or ambiguous in
# an MQTT topic segment, and a control character has no business in any of the
# three. Reject them at the door rather than letting them create an entry that
# cannot be addressed afterwards (issue #36). Quotes and accents are fine, the
# UI escapes them properly now.
_ILLEGAL_NAME_CHARS = ("/", "+", "#")


def _validate_device_name(name: str) -> str:
    """Return the cleaned name, or raise 400 if it cannot be used as a key."""
    cleaned = (name or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Device name must not be empty")
    bad = [c for c in _ILLEGAL_NAME_CHARS if c in cleaned]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"Device name must not contain {' or '.join(bad)} "
                   f"(these characters are not allowed in an MQTT topic)"
        )
    if any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
        raise HTTPException(status_code=400, detail="Device name must not contain control characters")
    return cleaned


def _build_discovery_configs(device, mqtt_handler, mapping_manager, device_manager):
    """Build the HA discovery configs for one device, multi-channel aware.

    Naming lives in mapping_manager so every publish path (this one and the
    startup republish in main.py) uses the same rules. See ADR-0007.
    """
    return mapping_manager.build_discovery_for_device(
        device, mqtt_handler.prefix,
        device_manager.get_devices_by_address(device.address)
    )


async def _publish_discovery(device, mqtt_handler, mapping_manager, device_manager):
    """Publish discovery configs + availability for one device."""
    configs = _build_discovery_configs(device, mqtt_handler, mapping_manager, device_manager)
    for item in configs:
        await mqtt_handler.publish_discovery_config(
            component=item["component"],
            unique_id=item["unique_id"],
            config=item["config"]
        )
    await mqtt_handler.publish_device_availability(device.name, available=True)
    return configs


@router.get("")
async def list_devices(request: Request) -> List[Dict[str, Any]]:
    """Get all devices"""
    device_manager = request.app.state.device_manager
    if not device_manager:
        raise HTTPException(status_code=500, detail="Device manager not initialized")

    return device_manager.get_all_devices()


@router.get("/search/{query}")
async def search_devices(query: str, request: Request) -> List[Dict[str, Any]]:
    """Search devices"""
    device_manager = request.app.state.device_manager
    if not device_manager:
        raise HTTPException(status_code=500, detail="Device manager not initialized")

    results = device_manager.search_devices(query)
    return [d.to_dict() for d in results]


# ":path" instead of a plain path parameter, because a device created before
# name validation existed may contain a slash. The server decodes the URL
# before routing, so "%2F" arrives as a real "/" and a plain "{name}" no longer
# matches: the request 404s with FastAPI's own "Not Found" and the device
# cannot be read, renamed or deleted at all (#36). New slashes stay rejected by
# _validate_device_name; this only keeps existing ones reachable so they can be
# renamed out.
@router.get("/{name:path}")
async def get_device(name: str, request: Request) -> Dict[str, Any]:
    """Get a specific device"""
    device_manager = request.app.state.device_manager
    if not device_manager:
        raise HTTPException(status_code=500, detail="Device manager not initialized")

    device = device_manager.get_device(name)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{name}' not found")

    return device.to_dict()


@router.post("")
async def create_device(device: DeviceCreate, request: Request) -> Dict[str, Any]:
    """Create a new device"""
    device_manager = request.app.state.device_manager
    if not device_manager:
        raise HTTPException(status_code=500, detail="Device manager not initialized")

    device.name = _validate_device_name(device.name)

    # Check if device already exists
    if device_manager.get_device(device.name):
        raise HTTPException(status_code=400, detail=f"Device '{device.name}' already exists")

    # Create device
    from core.device_manager import Device
    new_device = Device(
        name=device.name,
        address=device.address,
        rorg=device.rorg.upper().replace("0X", ""),
        func=device.func.upper().replace("0X", "").zfill(2),
        type=device.type.upper().replace("0X", "").zfill(2),
        sender_id=device.sender_id or "",
        description=device.description or "",
        room=device.room or "",
        manufacturer=device.manufacturer or "",
        actuator_type=device.actuator_type or "",
        invert=bool(device.invert),
        channel=int(device.channel or 0)
    )

    success = await device_manager.add_device(new_device)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create device")

    # Publish MQTT discovery. Re-publish every device on this address, not just
    # the new one, so an existing channel picks up multi-channel naming the
    # moment a second channel is added at the same address (#34, ADR-0005).
    mqtt_handler = request.app.state.mqtt_handler
    mapping_manager = request.app.state.mapping_manager
    if mqtt_handler and mapping_manager:
        try:
            for sibling in device_manager.get_devices_by_address(new_device.address):
                await _publish_discovery(sibling, mqtt_handler, mapping_manager, device_manager)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to publish discovery for {new_device.name}: {e}")

    return {"status": "created", "device": new_device.to_dict()}


@router.put("/{name:path}")  # see get_device for why ":path"
async def update_device(name: str, update: DeviceUpdate, request: Request) -> Dict[str, Any]:
    """Update a device"""
    device_manager = request.app.state.device_manager
    if not device_manager:
        raise HTTPException(status_code=500, detail="Device manager not initialized")

    device = device_manager.get_device(name)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{name}' not found")

    # Build update dict
    update_data = {}
    if update.address is not None:
        update_data["address"] = update.address
    if update.rorg is not None:
        update_data["rorg"] = update.rorg.upper().replace("0X", "")
    if update.func is not None:
        update_data["func"] = update.func.upper().replace("0X", "").zfill(2)
    if update.type is not None:
        update_data["type"] = update.type.upper().replace("0X", "").zfill(2)
    if update.sender_id is not None:
        update_data["sender_id"] = update.sender_id
    if update.description is not None:
        update_data["description"] = update.description
    if update.room is not None:
        update_data["room"] = update.room
    if update.manufacturer is not None:
        update_data["manufacturer"] = update.manufacturer
    if update.actuator_type is not None:
        update_data["actuator_type"] = update.actuator_type
    if update.invert is not None:
        update_data["invert"] = bool(update.invert)
    if update.channel is not None:
        update_data["channel"] = int(update.channel)

    # Snapshot the current discovery identity BEFORE mutating the device.
    # update_device mutates the Device in place, so we capture the old
    # unique_ids now to retract any entity whose unique_id changes on an
    # identity edit (address/sender/EEP/channel) instead of orphaning it in
    # HA. Passing channel is required or a channel-1 device is snapshotted
    # under the channel-0 unique_id. See ADR-0005 and issue #34.
    mqtt_handler = request.app.state.mqtt_handler
    mapping_manager = request.app.state.mapping_manager
    old_address = device.address
    old_configs: List[Dict[str, Any]] = []
    if mqtt_handler and mapping_manager:
        try:
            old_configs = _build_discovery_configs(device, mqtt_handler, mapping_manager, device_manager)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to snapshot old discovery for {name}: {e}")

    # Rename (re-key) if requested. The name is the primary key and the MQTT
    # topic base, so this is done after the old-discovery snapshot (to clean up
    # the old topics) and before the field update, so the rest of the flow uses
    # the new key. The HA unique_id does not depend on the name, so the entity
    # is preserved, only its topics/object_id change.
    old_name = name
    # Validate before comparing: " Salon " and "Salon" are the same name, and
    # the stripped form must not be treated as a rename onto itself (which
    # rename_device would reject as "already in use").
    if update.name is not None:
        update.name = _validate_device_name(update.name)
    if update.name is not None and update.name != name:
        if not await device_manager.rename_device(name, update.name):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot rename to '{update.name}': name is empty or already in use"
            )
        name = update.name

    success = await device_manager.update_device(name, update_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update device")

    # Re-publish MQTT discovery (important when EEP/channel/identity changes)
    updated_device = device_manager.get_device(name)
    if mqtt_handler and mapping_manager and updated_device:
        try:
            new_configs = _build_discovery_configs(updated_device, mqtt_handler, mapping_manager, device_manager)
            # Retract entities whose unique_id no longer exists after the edit
            # (empty-payload removal, same as delete_device) so stale entities
            # don't accumulate in HA (issue #34).
            new_uids = {item["unique_id"] for item in new_configs}
            for item in old_configs:
                if item["unique_id"] not in new_uids:
                    await mqtt_handler.remove_discovery_config(
                        component=item["component"],
                        unique_id=item["unique_id"]
                    )
            # Re-publish the edited device and every address-sibling (at both the
            # new and old address if it changed), so channel naming stays
            # consistent when a channel is added, removed, or re-homed
            # (#34, ADR-0005).
            to_publish = {d.name: d for d in device_manager.get_devices_by_address(updated_device.address)}
            for d in device_manager.get_devices_by_address(old_address):
                to_publish.setdefault(d.name, d)
            to_publish[updated_device.name] = updated_device
            for d in to_publish.values():
                await _publish_discovery(d, mqtt_handler, mapping_manager, device_manager)
            # A rename re-homes the topics, so everything retained under the
            # old name is now unreachable: its state, its availability, and its
            # entry in the state cache (which would otherwise republish the old
            # topic on every restart). Carry the last state over to the new name
            # first so the entity does not fall back to unknown (#36).
            if old_name != name:
                await mqtt_handler.rename_cached_state(old_name, name)
                await mqtt_handler.clear_device_topics(old_name)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to re-publish discovery for {name}: {e}")

    return {"status": "updated", "device": updated_device.to_dict()}


@router.delete("/{name:path}")  # see get_device for why ":path"
async def delete_device(name: str, request: Request) -> Dict[str, str]:
    """Delete a device"""
    device_manager = request.app.state.device_manager
    if not device_manager:
        raise HTTPException(status_code=500, detail="Device manager not initialized")

    device = device_manager.get_device(name)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{name}' not found")

    # Compute this device's discovery configs (multi-channel aware) before it
    # leaves the manager, so we know which unique_ids it owns.
    mqtt_handler = request.app.state.mqtt_handler
    mapping_manager = request.app.state.mapping_manager
    address = device.address
    removed_configs: List[Dict[str, Any]] = []
    if mqtt_handler and mapping_manager:
        try:
            removed_configs = _build_discovery_configs(device, mqtt_handler, mapping_manager, device_manager)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to compute discovery for {name}: {e}")

    success = await device_manager.delete_device(name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete device")

    if mqtt_handler and mapping_manager:
        try:
            # Keep any unique_id a surviving channel on the same address still
            # publishes (e.g. the shared RSSI/Last Seen sensors), and only
            # retract the ones now truly orphaned (#34, ADR-0005).
            survivors = device_manager.get_devices_by_address(address)
            keep_uids = set()
            for d in survivors:
                keep_uids.update(
                    item["unique_id"]
                    for item in _build_discovery_configs(d, mqtt_handler, mapping_manager, device_manager)
                )
            for item in removed_configs:
                if item["unique_id"] not in keep_uids:
                    await mqtt_handler.remove_discovery_config(
                        component=item["component"],
                        unique_id=item["unique_id"]
                    )
            # Re-publish survivors so a 2->1 transition drops the module naming.
            # This happens before the cleanup below because a shared sensor
            # (RSSI, Last Seen) may still be pointing at the deleted device's
            # state topic; republishing re-homes it to a surviving channel.
            for d in survivors:
                await _publish_discovery(d, mqtt_handler, mapping_manager, device_manager)
            # Now nothing references this name any more, so drop everything
            # retained under it plus its cached state. Without the cache part
            # the next restart would republish the state topic of a device that
            # no longer exists (#36).
            await mqtt_handler.clear_device_topics(device.name)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to remove discovery for {name}: {e}")

    return {"status": "deleted"}
