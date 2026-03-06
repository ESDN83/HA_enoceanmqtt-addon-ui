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
        actuator_type=device.actuator_type or ""
    )

    success = await device_manager.add_device(new_device)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create device")

    # Publish MQTT discovery
    mqtt_handler = request.app.state.mqtt_handler
    mapping_manager = request.app.state.mapping_manager
    if mqtt_handler and mapping_manager:
        try:
            device_info = mapping_manager.build_device_info(new_device)
            configs = mapping_manager.get_ha_discovery_configs(
                device_name=new_device.name,
                eep_id=new_device.eep_id,
                device_address=new_device.address,
                device_sender=new_device.sender_id,
                mqtt_prefix=mqtt_handler.prefix,
                device_info=device_info,
                actuator_type=new_device.actuator_type
            )
            for item in configs:
                await mqtt_handler.publish_discovery_config(
                    component=item["component"],
                    unique_id=item["unique_id"],
                    config=item["config"]
                )
            await mqtt_handler.publish_device_availability(new_device.name, available=True)
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

    success = await device_manager.update_device(name, update_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update device")

    # Re-publish MQTT discovery (important when EEP changes)
    updated_device = device_manager.get_device(name)
    mqtt_handler = request.app.state.mqtt_handler
    mapping_manager = request.app.state.mapping_manager
    if mqtt_handler and mapping_manager and updated_device:
        try:
            device_info = mapping_manager.build_device_info(updated_device)
            configs = mapping_manager.get_ha_discovery_configs(
                device_name=updated_device.name,
                eep_id=updated_device.eep_id,
                device_address=updated_device.address,
                device_sender=updated_device.sender_id,
                mqtt_prefix=mqtt_handler.prefix,
                device_info=device_info,
                actuator_type=updated_device.actuator_type
            )
            for item in configs:
                await mqtt_handler.publish_discovery_config(
                    component=item["component"],
                    unique_id=item["unique_id"],
                    config=item["config"]
                )
            await mqtt_handler.publish_device_availability(updated_device.name, available=True)
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

    # Remove MQTT discovery entities and set device offline
    mqtt_handler = request.app.state.mqtt_handler
    mapping_manager = request.app.state.mapping_manager
    if mqtt_handler and mapping_manager:
        try:
            device_info = mapping_manager.build_device_info(device)
            configs = mapping_manager.get_ha_discovery_configs(
                device_name=device.name,
                eep_id=device.eep_id,
                device_address=device.address,
                device_sender=device.sender_id,
                mqtt_prefix=mqtt_handler.prefix,
                device_info=device_info,
                actuator_type=device.actuator_type
            )
            # Remove each discovery config (publish empty payload)
            for item in configs:
                await mqtt_handler.remove_discovery_config(
                    component=item["component"],
                    unique_id=item["unique_id"]
                )
            # Set device offline
            await mqtt_handler.publish_device_availability(device.name, available=False)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to remove discovery for {name}: {e}")

    success = await device_manager.delete_device(name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete device")

    return {"status": "deleted"}
