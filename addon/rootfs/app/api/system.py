"""
System API - System status and configuration
"""

import os
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from typing import Dict, Any
import json
import yaml
import aiofiles
import zipfile
import io
from datetime import datetime

router = APIRouter()

# Version should match config.yaml
VERSION = "2.0.2"


@router.get("/status")
async def get_status(request: Request) -> Dict[str, Any]:
    """Get system status"""
    mqtt_handler = request.app.state.mqtt_handler
    serial_handler = request.app.state.serial_handler
    device_manager = request.app.state.device_manager
    eep_manager = request.app.state.eep_manager

    return {
        "mqtt": {
            "connected": mqtt_handler.is_connected if mqtt_handler else False,
            "host": os.getenv("MQTT_HOST", "not configured"),
            "prefix": os.getenv("MQTT_PREFIX", "enocean")
        },
        "enocean": {
            "connected": serial_handler.is_connected if serial_handler else False,
            "port": os.getenv("ENOCEAN_PORT", "not configured")
        },
        "devices": {
            "count": device_manager.device_count if device_manager else 0
        },
        "profiles": {
            "count": eep_manager.profile_count if eep_manager else 0
        },
        "version": VERSION
    }


@router.get("/config")
async def get_config(request: Request) -> Dict[str, Any]:
    """Get current configuration"""
    return {
        "mqtt": {
            "host": os.getenv("MQTT_HOST", ""),
            "port": os.getenv("MQTT_PORT", "1883"),
            "prefix": os.getenv("MQTT_PREFIX", "enocean"),
            "discovery_prefix": os.getenv("MQTT_DISCOVERY_PREFIX", "homeassistant"),
            "client_id": os.getenv("MQTT_CLIENT_ID", "enocean_gateway")
        },
        "enocean": {
            "port": os.getenv("ENOCEAN_PORT", "")
        },
        "logging": {
            "level": os.getenv("LOG_LEVEL", "info")
        },
        "paths": {
            "config": request.app.state.config_path
        }
    }


@router.get("/logs")
async def get_logs(lines: int = 100, request: Request = None) -> Dict[str, Any]:
    """Get recent log entries"""
    # In a real implementation, this would read from a log file
    # For now, return placeholder
    return {
        "logs": [],
        "message": "Log streaming not yet implemented"
    }


@router.post("/export")
async def export_all(request: Request):
    """Export all configuration as ZIP file"""
    config_path = request.app.state.config_path

    # Create in-memory ZIP file
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Export devices
        devices_file = os.path.join(config_path, "devices.json")
        if os.path.exists(devices_file):
            zf.write(devices_file, "devices.json")

        # Export legacy devices format
        legacy_devices = os.path.join(config_path, "enoceanmqtt.devices")
        if os.path.exists(legacy_devices):
            zf.write(legacy_devices, "enoceanmqtt.devices")

        # Export mappings
        mappings_file = os.path.join(config_path, "mapping.yaml")
        if os.path.exists(mappings_file):
            zf.write(mappings_file, "mapping.yaml")

        # Export custom EEP profiles
        custom_eep_path = os.path.join(config_path, "custom_eep")
        if os.path.exists(custom_eep_path):
            for filename in os.listdir(custom_eep_path):
                if filename.endswith(".yaml"):
                    filepath = os.path.join(custom_eep_path, filename)
                    zf.write(filepath, f"custom_eep/{filename}")

        # Add export metadata
        metadata = {
            "exported_at": datetime.now().isoformat(),
            "version": VERSION,
            "device_manager": request.app.state.device_manager.device_count if request.app.state.device_manager else 0,
            "eep_manager": request.app.state.eep_manager.profile_count if request.app.state.eep_manager else 0
        }
        zf.writestr("export_info.json", json.dumps(metadata, indent=2))

    zip_buffer.seek(0)

    filename = f"enocean_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/import")
async def import_all(file: UploadFile = File(...), request: Request = None) -> Dict[str, Any]:
    """Import configuration from ZIP file"""
    if not request:
        raise HTTPException(status_code=500, detail="Request context required")

    config_path = request.app.state.config_path
    device_manager = request.app.state.device_manager

    try:
        content = await file.read()
        zip_buffer = io.BytesIO(content)

        imported = {
            "devices": False,
            "mappings": False,
            "custom_profiles": 0
        }

        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            for filename in zf.namelist():
                if filename == "devices.json":
                    # Import devices
                    devices_data = json.loads(zf.read(filename))
                    devices_file = os.path.join(config_path, "devices.json")
                    os.makedirs(config_path, exist_ok=True)
                    async with aiofiles.open(devices_file, 'w') as f:
                        await f.write(json.dumps(devices_data, indent=2))
                    imported["devices"] = True

                    # Reload devices
                    if device_manager:
                        await device_manager.load_devices()

                elif filename == "mapping.yaml":
                    # Import mappings
                    mappings_data = zf.read(filename)
                    mappings_file = os.path.join(config_path, "mapping.yaml")
                    os.makedirs(config_path, exist_ok=True)
                    async with aiofiles.open(mappings_file, 'wb') as f:
                        await f.write(mappings_data)
                    imported["mappings"] = True

                elif filename.startswith("custom_eep/") and filename.endswith(".yaml"):
                    # Import custom profiles
                    profile_data = zf.read(filename)
                    profile_name = os.path.basename(filename)
                    custom_path = os.path.join(config_path, "custom_eep")
                    os.makedirs(custom_path, exist_ok=True)
                    async with aiofiles.open(os.path.join(custom_path, profile_name), 'wb') as f:
                        await f.write(profile_data)
                    imported["custom_profiles"] += 1

        return {"status": "imported", "details": imported}

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")


@router.post("/restart")
async def restart_services(request: Request) -> Dict[str, str]:
    """Restart EnOcean and MQTT services"""
    mqtt_handler = request.app.state.mqtt_handler
    serial_handler = request.app.state.serial_handler

    try:
        # Disconnect
        if serial_handler and serial_handler.is_connected:
            await serial_handler.disconnect()

        if mqtt_handler and mqtt_handler.is_connected:
            await mqtt_handler.disconnect()

        # Reconnect
        if mqtt_handler:
            await mqtt_handler.connect()

        if serial_handler:
            await serial_handler.connect()

        return {"status": "restarted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restart failed: {e}")
