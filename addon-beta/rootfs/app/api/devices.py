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


def _discovery_naming(device, device_manager):
    """Return (entity_name, module_name) for a device's discovery configs.

    When several devices share one address they are the channels of one
    multi-channel module (ADR-0005): they collapse to a single HA device
    (identifiers = address). Each channel entity must therefore carry its own
    name while the shared HA device carries a stable module label, or both
    channels show the same name (issue #34). Single-address devices keep the
    previous behaviour (entity name = None -> HA device name).
    """
    if len(device_manager.get_devices_by_address(device.address)) > 1:
        entity_name = device.description or device.name
        module_name = (f"{device.manufacturer} {device.eep_id}".strip()
                       or f"EnOcean {device.eep_id}")
        return entity_name, module_name
    return None, None


def _build_discovery_configs(device, mqtt_handler, mapping_manager, device_manager):
    """Build the HA discovery configs for one device, multi-channel aware."""
    entity_name, module_name = _discovery_naming(device, device_manager)
    device_info = mapping_manager.build_device_info(device, module_name=module_name)
    return mapping_manager.get_ha_discovery_configs(
        device_name=device.name,
        eep_id=device.eep_id,
        device_address=device.address,
        device_sender=device.sender_id,
        mqtt_prefix=mqtt_handler.prefix,
        device_info=device_info,
        actuator_type=device.actuator_type,
        invert=device.invert,
        channel=device.channel,
        entity_name=entity_name,
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


@router.get("/{name}")
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


@router.put("/{name}")
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
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to re-publish discovery for {name}: {e}")

    return {"status": "updated", "device": updated_device.to_dict()}


@router.delete("/{name}")
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
            await mqtt_handler.publish_device_availability(device.name, available=False)
            # Re-publish survivors so a 2->1 transition drops the module naming.
            for d in survivors:
                await _publish_discovery(d, mqtt_handler, mapping_manager, device_manager)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to remove discovery for {name}: {e}")

    return {"status": "deleted"}
