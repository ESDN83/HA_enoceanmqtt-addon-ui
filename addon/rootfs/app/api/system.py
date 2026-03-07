"""
System API - System status and configuration
"""

import os
import logging
import shutil
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from typing import Dict, Any, List
import json
import yaml
import aiofiles
import zipfile
import io
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()



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
        "version": request.app.version
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
            "version": request.app.version,
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
            for zip_entry in zf.namelist():
                # Strip any folder prefix (e.g., "enocean_config_20260306_172102/devices.json" -> "devices.json")
                # This makes import work with both flat and nested zip structures
                basename = os.path.basename(zip_entry)
                # For custom_eep paths, check if "custom_eep/" appears anywhere in the path
                is_custom_eep = "custom_eep/" in zip_entry and zip_entry.endswith(".yaml")

                if basename == "devices.json":
                    # Import devices
                    devices_data = json.loads(zf.read(zip_entry))
                    devices_file = os.path.join(config_path, "devices.json")
                    os.makedirs(config_path, exist_ok=True)
                    async with aiofiles.open(devices_file, 'w') as f:
                        await f.write(json.dumps(devices_data, indent=2))
                    imported["devices"] = True

                    # Reload devices
                    if device_manager:
                        await device_manager.load_devices()

                elif basename == "mapping.yaml":
                    # Import mappings
                    mappings_data = zf.read(zip_entry)
                    mappings_file = os.path.join(config_path, "mapping.yaml")
                    os.makedirs(config_path, exist_ok=True)
                    async with aiofiles.open(mappings_file, 'wb') as f:
                        await f.write(mappings_data)
                    imported["mappings"] = True

                elif is_custom_eep:
                    # Import custom profiles
                    profile_data = zf.read(zip_entry)
                    profile_name = basename
                    custom_path = os.path.join(config_path, "custom_eep")
                    os.makedirs(custom_path, exist_ok=True)
                    async with aiofiles.open(os.path.join(custom_path, profile_name), 'wb') as f:
                        await f.write(profile_data)
                    imported["custom_profiles"] += 1

        # Reload EEP manager if custom profiles were imported
        if imported["custom_profiles"] > 0:
            eep_manager = request.app.state.eep_manager
            if eep_manager:
                await eep_manager._load_custom_profiles()

        # Reload mapping manager if mappings were imported
        if imported["mappings"]:
            mapping_manager = request.app.state.mapping_manager
            if mapping_manager:
                await mapping_manager.initialize()

        # Re-publish MQTT discovery for all devices after import
        if imported["devices"] or imported["custom_profiles"]:
            mqtt_handler = request.app.state.mqtt_handler
            mapping_manager = request.app.state.mapping_manager
            if mqtt_handler and device_manager and mapping_manager:
                for device in device_manager.devices.values():
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
                        for item in configs:
                            await mqtt_handler.publish_discovery_config(
                                component=item["component"],
                                unique_id=item["unique_id"],
                                config=item["config"]
                            )
                        await mqtt_handler.publish_device_availability(device.name, available=True)
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Failed to publish discovery for {device.name}: {e}")

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


# ===== Backup Management =====

BACKUP_DIR_NAME = "backups"


def _get_backup_dir(config_path: str) -> str:
    """Get backup directory path, creating it if needed"""
    backup_dir = os.path.join(config_path, BACKUP_DIR_NAME)
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


@router.post("/backup")
async def create_backup(request: Request) -> Dict[str, Any]:
    """Create a local backup ZIP of all configuration"""
    config_path = request.app.state.config_path
    backup_dir = _get_backup_dir(config_path)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"enocean_backup_{timestamp}.zip"
    filepath = os.path.join(backup_dir, filename)

    try:
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Backup devices
            devices_file = os.path.join(config_path, "devices.json")
            if os.path.exists(devices_file):
                zf.write(devices_file, "devices.json")

            # Backup legacy devices format
            legacy_devices = os.path.join(config_path, "enoceanmqtt.devices")
            if os.path.exists(legacy_devices):
                zf.write(legacy_devices, "enoceanmqtt.devices")

            # Backup mappings
            mappings_file = os.path.join(config_path, "mapping.yaml")
            if os.path.exists(mappings_file):
                zf.write(mappings_file, "mapping.yaml")

            # Backup custom EEP profiles
            custom_eep_path = os.path.join(config_path, "custom_eep")
            if os.path.exists(custom_eep_path):
                for fname in os.listdir(custom_eep_path):
                    if fname.endswith(".yaml"):
                        fpath = os.path.join(custom_eep_path, fname)
                        zf.write(fpath, f"custom_eep/{fname}")

            # Backup cached states
            states_file = os.path.join(config_path, "last_states.json")
            if os.path.exists(states_file):
                zf.write(states_file, "last_states.json")

            # Add backup metadata
            metadata = {
                "created_at": datetime.now().isoformat(),
                "version": request.app.version,
                "devices": request.app.state.device_manager.device_count if request.app.state.device_manager else 0,
                "profiles": request.app.state.eep_manager.profile_count if request.app.state.eep_manager else 0
            }
            zf.writestr("backup_info.json", json.dumps(metadata, indent=2))

        size = os.path.getsize(filepath)
        logger.info(f"Backup created: {filename} ({size} bytes)")

        return {
            "status": "created",
            "filename": filename,
            "size": size,
            "created_at": datetime.now().isoformat()
        }

    except Exception as e:
        # Clean up partial file
        if os.path.exists(filepath):
            os.remove(filepath)
        logger.error(f"Backup creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backup failed: {e}")


@router.get("/backups")
async def list_backups(request: Request) -> List[Dict[str, Any]]:
    """List all local backup ZIP files"""
    config_path = request.app.state.config_path
    backup_dir = _get_backup_dir(config_path)

    backups = []
    for fname in sorted(os.listdir(backup_dir), reverse=True):
        if fname.endswith(".zip"):
            fpath = os.path.join(backup_dir, fname)
            stat = os.stat(fpath)

            # Try to read backup metadata
            metadata = {}
            try:
                with zipfile.ZipFile(fpath, 'r') as zf:
                    if "backup_info.json" in zf.namelist():
                        metadata = json.loads(zf.read("backup_info.json"))
                    elif "export_info.json" in zf.namelist():
                        metadata = json.loads(zf.read("export_info.json"))
            except Exception:
                pass

            backups.append({
                "filename": fname,
                "size": stat.st_size,
                "created_at": metadata.get("created_at") or metadata.get("exported_at")
                              or datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "version": metadata.get("version", "unknown"),
                "devices": metadata.get("devices", metadata.get("device_manager", "?")),
                "profiles": metadata.get("profiles", metadata.get("eep_manager", "?"))
            })

    return backups


@router.post("/backup/restore/{filename}")
async def restore_backup(filename: str, request: Request) -> Dict[str, Any]:
    """Restore configuration from a local backup ZIP file.

    This reuses the existing /import logic but reads from the local backup directory.
    """
    config_path = request.app.state.config_path
    backup_dir = _get_backup_dir(config_path)

    # Security: prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join(backup_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Backup not found")

    device_manager = request.app.state.device_manager

    try:
        imported = {
            "devices": False,
            "mappings": False,
            "custom_profiles": 0
        }

        with zipfile.ZipFile(filepath, 'r') as zf:
            for zip_entry in zf.namelist():
                basename = os.path.basename(zip_entry)
                is_custom_eep = "custom_eep/" in zip_entry and zip_entry.endswith(".yaml")

                if basename == "devices.json":
                    devices_data = json.loads(zf.read(zip_entry))
                    devices_file = os.path.join(config_path, "devices.json")
                    async with aiofiles.open(devices_file, 'w') as f:
                        await f.write(json.dumps(devices_data, indent=2))
                    imported["devices"] = True
                    if device_manager:
                        await device_manager.load_devices()

                elif basename == "mapping.yaml":
                    mappings_data = zf.read(zip_entry)
                    mappings_file = os.path.join(config_path, "mapping.yaml")
                    async with aiofiles.open(mappings_file, 'wb') as f:
                        await f.write(mappings_data)
                    imported["mappings"] = True

                elif basename == "last_states.json":
                    states_data = zf.read(zip_entry)
                    states_file = os.path.join(config_path, "last_states.json")
                    async with aiofiles.open(states_file, 'wb') as f:
                        await f.write(states_data)

                elif is_custom_eep:
                    profile_data = zf.read(zip_entry)
                    profile_name = basename
                    custom_path = os.path.join(config_path, "custom_eep")
                    os.makedirs(custom_path, exist_ok=True)
                    async with aiofiles.open(os.path.join(custom_path, profile_name), 'wb') as f:
                        await f.write(profile_data)
                    imported["custom_profiles"] += 1

        # Reload managers
        if imported["custom_profiles"] > 0:
            eep_manager = request.app.state.eep_manager
            if eep_manager:
                await eep_manager._load_custom_profiles()

        if imported["mappings"]:
            mapping_manager = request.app.state.mapping_manager
            if mapping_manager:
                await mapping_manager.initialize()

        # Re-publish MQTT discovery
        if imported["devices"] or imported["custom_profiles"]:
            mqtt_handler = request.app.state.mqtt_handler
            mapping_manager = request.app.state.mapping_manager
            if mqtt_handler and device_manager and mapping_manager:
                for device in device_manager.devices.values():
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
                        for item in configs:
                            await mqtt_handler.publish_discovery_config(
                                component=item["component"],
                                unique_id=item["unique_id"],
                                config=item["config"]
                            )
                        await mqtt_handler.publish_device_availability(device.name, available=True)
                    except Exception as e:
                        logger.error(f"Failed to publish discovery for {device.name}: {e}")

        logger.info(f"Backup restored: {filename} → {imported}")
        return {"status": "restored", "filename": filename, "details": imported}

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")


@router.delete("/backup/{filename}")
async def delete_backup(filename: str, request: Request) -> Dict[str, str]:
    """Delete a local backup file"""
    config_path = request.app.state.config_path
    backup_dir = _get_backup_dir(config_path)

    # Security: prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join(backup_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Backup not found")

    try:
        os.remove(filepath)
        logger.info(f"Backup deleted: {filename}")
        return {"status": "deleted", "filename": filename}
    except Exception as e:
        logger.error(f"Failed to delete backup: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


@router.get("/backup/download/{filename}")
async def download_backup(filename: str, request: Request):
    """Download a backup file"""
    config_path = request.app.state.config_path
    backup_dir = _get_backup_dir(config_path)

    # Security: prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join(backup_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Backup not found")

    return FileResponse(
        filepath,
        media_type="application/zip",
        filename=filename
    )
