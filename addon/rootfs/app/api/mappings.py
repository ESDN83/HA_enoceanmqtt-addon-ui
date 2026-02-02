"""
Mappings API - MQTT/HA entity mappings management
"""

import os
import shutil
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import yaml
import aiofiles

router = APIRouter()

MAX_VERSIONS = 3  # Keep last 3 versions for rollback


class MappingUpdate(BaseModel):
    """Mapping update model"""
    eep_id: str
    mappings: Dict[str, Dict[str, Any]]


async def _create_backup(config_path: str, mappings_file: str):
    """Create a backup before saving, rotating old versions"""
    if not os.path.exists(mappings_file):
        return

    # Rotate existing backups (v3 -> delete, v2 -> v3, v1 -> v2, current -> v1)
    for i in range(MAX_VERSIONS, 0, -1):
        old_backup = os.path.join(config_path, f"mapping.yaml.v{i}")
        if i == MAX_VERSIONS:
            if os.path.exists(old_backup):
                os.remove(old_backup)
        else:
            new_backup = os.path.join(config_path, f"mapping.yaml.v{i+1}")
            if os.path.exists(old_backup):
                shutil.move(old_backup, new_backup)

    # Copy current to v1
    backup_file = os.path.join(config_path, "mapping.yaml.v1")
    shutil.copy2(mappings_file, backup_file)


@router.get("")
async def get_all_mappings(request: Request) -> Dict[str, Any]:
    """Get all mappings with metadata"""
    config_path = request.app.state.config_path
    mappings_file = os.path.join(config_path, "mapping.yaml")

    result = {
        "mappings": {},
        "metadata": {
            "last_modified": None,
            "versions_available": []
        }
    }

    # Get available backup versions
    for i in range(1, MAX_VERSIONS + 1):
        backup_file = os.path.join(config_path, f"mapping.yaml.v{i}")
        if os.path.exists(backup_file):
            mtime = os.path.getmtime(backup_file)
            result["metadata"]["versions_available"].append({
                "version": i,
                "date": datetime.fromtimestamp(mtime).isoformat()
            })

    if not os.path.exists(mappings_file):
        return result

    try:
        # Get last modified time
        mtime = os.path.getmtime(mappings_file)
        result["metadata"]["last_modified"] = datetime.fromtimestamp(mtime).isoformat()

        async with aiofiles.open(mappings_file, 'r') as f:
            content = await f.read()
            result["mappings"] = yaml.safe_load(content) or {}
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read mappings: {e}")


@router.get("/{eep_id}")
async def get_mapping(eep_id: str, request: Request) -> Dict[str, Any]:
    """Get mapping for a specific EEP"""
    config_path = request.app.state.config_path
    mappings_file = os.path.join(config_path, "mapping.yaml")

    if not os.path.exists(mappings_file):
        return {}

    try:
        async with aiofiles.open(mappings_file, 'r') as f:
            content = await f.read()
            data = yaml.safe_load(content) or {}

            # Check for EEP-specific mapping
            if eep_id in data:
                return data[eep_id]

            # Return common mappings as fallback
            return data.get("common", {})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read mapping: {e}")


@router.put("/{eep_id}")
async def update_mapping(eep_id: str, mapping: MappingUpdate, request: Request) -> Dict[str, str]:
    """Update mapping for a specific EEP"""
    config_path = request.app.state.config_path
    mappings_file = os.path.join(config_path, "mapping.yaml")

    try:
        # Create backup before modifying
        await _create_backup(config_path, mappings_file)

        # Load existing mappings
        data = {}
        if os.path.exists(mappings_file):
            async with aiofiles.open(mappings_file, 'r') as f:
                content = await f.read()
                data = yaml.safe_load(content) or {}

        # Update mapping
        data[eep_id] = mapping.mappings

        # Save
        os.makedirs(config_path, exist_ok=True)
        async with aiofiles.open(mappings_file, 'w') as f:
            await f.write(yaml.dump(data, default_flow_style=False, allow_unicode=True))

        return {"status": "updated"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update mapping: {e}")


@router.post("/restore/{version}")
async def restore_mapping_version(version: int, request: Request) -> Dict[str, str]:
    """Restore mappings from a previous version"""
    if version < 1 or version > MAX_VERSIONS:
        raise HTTPException(status_code=400, detail=f"Version must be between 1 and {MAX_VERSIONS}")

    config_path = request.app.state.config_path
    mappings_file = os.path.join(config_path, "mapping.yaml")
    backup_file = os.path.join(config_path, f"mapping.yaml.v{version}")

    if not os.path.exists(backup_file):
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    try:
        # Create backup of current before restoring
        await _create_backup(config_path, mappings_file)

        # Restore from backup
        shutil.copy2(backup_file, mappings_file)

        return {"status": "restored", "version": version}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restore: {e}")


@router.put("/save")
async def save_all_mappings(request: Request, data: Dict[str, Any]) -> Dict[str, str]:
    """Save complete mappings (for editor)"""
    config_path = request.app.state.config_path
    mappings_file = os.path.join(config_path, "mapping.yaml")

    try:
        # Create backup before saving
        await _create_backup(config_path, mappings_file)

        # Save new mappings
        os.makedirs(config_path, exist_ok=True)
        async with aiofiles.open(mappings_file, 'w') as f:
            await f.write(yaml.dump(data, default_flow_style=False, allow_unicode=True))

        return {"status": "saved"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save mappings: {e}")


@router.delete("/{eep_id}")
async def delete_mapping(eep_id: str, request: Request) -> Dict[str, str]:
    """Delete mapping for a specific EEP"""
    config_path = request.app.state.config_path
    mappings_file = os.path.join(config_path, "mapping.yaml")

    if not os.path.exists(mappings_file):
        raise HTTPException(status_code=404, detail="No mappings file found")

    try:
        async with aiofiles.open(mappings_file, 'r') as f:
            content = await f.read()
            data = yaml.safe_load(content) or {}

        if eep_id not in data:
            raise HTTPException(status_code=404, detail=f"Mapping for '{eep_id}' not found")

        del data[eep_id]

        async with aiofiles.open(mappings_file, 'w') as f:
            await f.write(yaml.dump(data, default_flow_style=False, allow_unicode=True))

        return {"status": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete mapping: {e}")


@router.post("/import")
async def import_mappings(file: UploadFile = File(...), request: Request = None) -> Dict[str, Any]:
    """Import mappings from YAML file"""
    if not request:
        raise HTTPException(status_code=500, detail="Request context required")

    config_path = request.app.state.config_path

    try:
        content = await file.read()
        data = yaml.safe_load(content)

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Invalid mapping format")

        mappings_file = os.path.join(config_path, "mapping.yaml")

        # Merge with existing
        existing = {}
        if os.path.exists(mappings_file):
            async with aiofiles.open(mappings_file, 'r') as f:
                existing_content = await f.read()
                existing = yaml.safe_load(existing_content) or {}

        existing.update(data)

        os.makedirs(config_path, exist_ok=True)
        async with aiofiles.open(mappings_file, 'w') as f:
            await f.write(yaml.dump(existing, default_flow_style=False, allow_unicode=True))

        return {"status": "imported", "count": len(data)}

    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import mappings: {e}")


@router.get("/export/download")
async def export_mappings(request: Request):
    """Export mappings as YAML file"""
    config_path = request.app.state.config_path
    mappings_file = os.path.join(config_path, "mapping.yaml")

    if not os.path.exists(mappings_file):
        raise HTTPException(status_code=404, detail="No mappings file found")

    return FileResponse(
        mappings_file,
        media_type="application/x-yaml",
        filename="mapping.yaml"
    )


@router.get("/templates")
async def get_mapping_templates() -> Dict[str, Any]:
    """Get predefined mapping templates for common device types"""
    return {
        "temperature_sensor": {
            "TMP": {
                "component": "sensor",
                "name": "Temperature",
                "device_class": "temperature",
                "unit_of_measurement": "°C",
                "icon": "mdi:thermometer"
            }
        },
        "humidity_sensor": {
            "HUM": {
                "component": "sensor",
                "name": "Humidity",
                "device_class": "humidity",
                "unit_of_measurement": "%",
                "icon": "mdi:water-percent"
            }
        },
        "contact_sensor": {
            "CO": {
                "component": "binary_sensor",
                "name": "Contact",
                "device_class": "door",
                "icon": "mdi:door"
            }
        },
        "occupancy_sensor": {
            "OCC": {
                "component": "binary_sensor",
                "name": "Occupancy",
                "device_class": "occupancy",
                "icon": "mdi:motion-sensor"
            }
        },
        "switch": {
            "state": {
                "component": "switch",
                "name": "Switch",
                "icon": "mdi:light-switch"
            }
        },
        "dimmer": {
            "DIM": {
                "component": "light",
                "name": "Dimmer",
                "brightness": True,
                "icon": "mdi:brightness-6"
            }
        },
        "cover": {
            "POS": {
                "component": "cover",
                "name": "Cover",
                "device_class": "blind",
                "icon": "mdi:blinds"
            }
        },
        "kessel_staufix": {
            "AL": {
                "component": "binary_sensor",
                "name": "Alarm",
                "device_class": "problem",
                "icon": "mdi:pipe-valve"
            }
        },
        "common": {
            "rssi": {
                "component": "sensor",
                "name": "RSSI",
                "device_class": "signal_strength",
                "unit_of_measurement": "dBm",
                "icon": "mdi:wifi"
            },
            "last_update": {
                "component": "sensor",
                "name": "Last Update",
                "device_class": "timestamp",
                "icon": "mdi:clock"
            }
        }
    }
