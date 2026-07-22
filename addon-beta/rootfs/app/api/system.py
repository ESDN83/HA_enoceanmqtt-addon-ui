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
from lxml import etree

router = APIRouter()

# Single source of truth (reads config.yaml) — no manual bumping needed here.
from app_version import VERSION


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
        devices_file = os.path.join(config_path, "devices.yaml")
        if os.path.exists(devices_file):
            zf.write(devices_file, "devices.yaml")

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

        # Export user EEP.xml if exists
        user_eep = os.path.join(config_path, "EEP.xml")
        if os.path.exists(user_eep):
            zf.write(user_eep, "EEP.xml")

        # Export mapping overrides
        overrides_file = os.path.join(config_path, "mapping_overrides.yaml")
        if os.path.exists(overrides_file):
            zf.write(overrides_file, "mapping_overrides.yaml")

        # Add export metadata
        metadata = {
            "exported_at": datetime.now().isoformat(),
            "version": VERSION,
            "device_manager": request.app.state.device_manager.device_count if request.app.state.device_manager else 0,
            "eep_manager": request.app.state.eep_manager.profile_count if request.app.state.eep_manager else 0
        }
        zf.writestr("export_info.yaml", yaml.dump(metadata, default_flow_style=False, allow_unicode=True))

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
            "mapping_overrides": False,
            "custom_profiles": 0,
            "eep_xml": False
        }

        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            for filename in zf.namelist():
                if filename in ("devices.json", "devices.yaml"):
                    # Import devices (support both old JSON and new YAML)
                    raw = zf.read(filename)
                    if filename.endswith(".json"):
                        devices_data = json.loads(raw)
                    else:
                        devices_data = yaml.safe_load(raw) or {}
                    devices_file = os.path.join(config_path, "devices.yaml")
                    os.makedirs(config_path, exist_ok=True)
                    async with aiofiles.open(devices_file, 'w') as f:
                        await f.write(yaml.dump(devices_data, default_flow_style=False, allow_unicode=True))
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

                elif filename == "EEP.xml":
                    # Import user EEP.xml
                    eep_data = zf.read(filename)
                    eep_path = os.path.join(config_path, "EEP.xml")
                    os.makedirs(config_path, exist_ok=True)
                    async with aiofiles.open(eep_path, 'wb') as f:
                        await f.write(eep_data)
                    imported["eep_xml"] = True

                elif filename in ("mapping_overrides.json", "mapping_overrides.yaml"):
                    # Import mapping overrides (support both old JSON and new YAML)
                    raw = zf.read(filename)
                    if filename.endswith(".json"):
                        overrides_data = json.loads(raw)
                    else:
                        overrides_data = yaml.safe_load(raw) or {}
                    overrides_path = os.path.join(config_path, "mapping_overrides.yaml")
                    os.makedirs(config_path, exist_ok=True)
                    async with aiofiles.open(overrides_path, 'w') as f:
                        await f.write(yaml.dump(overrides_data, default_flow_style=False, allow_unicode=True))
                    imported["mapping_overrides"] = True

        # Reinitialize EEP manager if any EEP-related data was imported
        eep_manager = request.app.state.eep_manager
        if eep_manager and (imported.get("eep_xml") or imported.get("custom_profiles", 0) > 0):
            eep_manager.profiles.clear()
            await eep_manager.initialize()

        # Reload mapping overrides into cache after import
        if imported.get("mapping_overrides") and eep_manager:
            await eep_manager._load_overrides()

        return {"status": "imported", "details": imported}

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")


@router.get("/eep-info")
async def get_eep_info(request: Request) -> Dict[str, Any]:
    """Get EEP.xml status information"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP Manager not initialized")
    return eep_manager.get_eep_info()


@router.post("/upload-eep")
async def upload_eep(file: UploadFile = File(...), request: Request = None) -> Dict[str, Any]:
    """Upload custom EEP.xml file"""
    if not request:
        raise HTTPException(status_code=500, detail="Request context required")

    config_path = request.app.state.config_path
    eep_manager = request.app.state.eep_manager

    try:
        content = await file.read()

        # Validate XML
        try:
            root = etree.fromstring(content)
            # Basic structure check - should have telegram elements
            telegrams = root.findall(".//telegram")
            if not telegrams:
                raise HTTPException(status_code=400, detail="Invalid EEP.xml: no telegram elements found")
        except etree.XMLSyntaxError as e:
            raise HTTPException(status_code=400, detail=f"Invalid XML: {e}")

        # Save to config path
        eep_path = os.path.join(config_path, "EEP.xml")
        os.makedirs(config_path, exist_ok=True)
        async with aiofiles.open(eep_path, 'wb') as f:
            await f.write(content)

        # Reload EEP profiles
        if eep_manager:
            eep_manager.profiles.clear()
            await eep_manager.initialize()

        return {
            "status": "uploaded",
            "info": eep_manager.get_eep_info() if eep_manager else {}
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.delete("/delete-eep")
async def delete_eep(request: Request) -> Dict[str, Any]:
    """Delete custom EEP.xml and revert to bundled"""
    config_path = request.app.state.config_path
    eep_manager = request.app.state.eep_manager

    eep_path = os.path.join(config_path, "EEP.xml")

    if not os.path.exists(eep_path):
        raise HTTPException(status_code=404, detail="No custom EEP.xml found")

    try:
        os.remove(eep_path)

        # Reload EEP profiles (will fall back to bundled)
        if eep_manager:
            eep_manager.profiles.clear()
            await eep_manager.initialize()

        return {
            "status": "deleted",
            "info": eep_manager.get_eep_info() if eep_manager else {}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


BACKUP_DIR = "backups"


def _get_backup_dir(config_path: str) -> str:
    """Get backup directory path, creating it if needed"""
    backup_dir = os.path.join(config_path, BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


@router.get("/backups")
async def list_backups(request: Request):
    """List all local backups"""
    config_path = request.app.state.config_path
    backup_dir = _get_backup_dir(config_path)
    backups = []

    for filename in sorted(os.listdir(backup_dir), reverse=True):
        if not filename.endswith(".zip"):
            continue
        filepath = os.path.join(backup_dir, filename)
        stat = os.stat(filepath)

        # Try to read metadata from ZIP
        devices = 0
        version = "?"
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                if "export_info.yaml" in zf.namelist():
                    meta = yaml.safe_load(zf.read("export_info.yaml"))
                    devices = meta.get("device_manager", 0)
                    version = meta.get("version", "?")
                elif "export_info.json" in zf.namelist():
                    meta = json.loads(zf.read("export_info.json"))
                    devices = meta.get("device_manager", 0)
                    version = meta.get("version", "?")
        except Exception:
            pass

        backups.append({
            "filename": filename,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size": stat.st_size,
            "devices": devices,
            "version": version,
        })

    return backups


@router.post("/backup")
async def create_backup(request: Request) -> Dict[str, Any]:
    """Create a local backup ZIP"""
    config_path = request.app.state.config_path
    backup_dir = _get_backup_dir(config_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.zip"
    filepath = os.path.join(backup_dir, filename)

    device_manager = request.app.state.device_manager
    eep_manager = request.app.state.eep_manager

    with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Devices
        devices_file = os.path.join(config_path, "devices.yaml")
        if os.path.exists(devices_file):
            zf.write(devices_file, "devices.yaml")

        # Legacy devices
        legacy_devices = os.path.join(config_path, "enoceanmqtt.devices")
        if os.path.exists(legacy_devices):
            zf.write(legacy_devices, "enoceanmqtt.devices")

        # Mappings
        mappings_file = os.path.join(config_path, "mapping.yaml")
        if os.path.exists(mappings_file):
            zf.write(mappings_file, "mapping.yaml")

        # Custom EEP profiles
        custom_eep_path = os.path.join(config_path, "custom_eep")
        if os.path.exists(custom_eep_path):
            for fname in os.listdir(custom_eep_path):
                if fname.endswith(".yaml"):
                    zf.write(os.path.join(custom_eep_path, fname), f"custom_eep/{fname}")

        # User EEP.xml
        user_eep = os.path.join(config_path, "EEP.xml")
        if os.path.exists(user_eep):
            zf.write(user_eep, "EEP.xml")

        # Mapping overrides
        overrides_file = os.path.join(config_path, "mapping_overrides.yaml")
        if os.path.exists(overrides_file):
            zf.write(overrides_file, "mapping_overrides.yaml")

        # Metadata
        metadata = {
            "exported_at": datetime.now().isoformat(),
            "version": VERSION,
            "device_manager": device_manager.device_count if device_manager else 0,
            "eep_manager": eep_manager.profile_count if eep_manager else 0
        }
        zf.writestr("export_info.yaml", yaml.dump(metadata, default_flow_style=False, allow_unicode=True))

    return {"filename": filename, "status": "created"}


@router.get("/backup/download/{filename}")
async def download_backup(filename: str, request: Request):
    """Download a backup file"""
    config_path = request.app.state.config_path
    filepath = os.path.join(_get_backup_dir(config_path), filename)

    if not os.path.exists(filepath) or not filename.endswith(".zip"):
        raise HTTPException(status_code=404, detail="Backup not found")

    return FileResponse(filepath, filename=filename, media_type="application/zip")


@router.post("/backup/restore/{filename}")
async def restore_backup(filename: str, request: Request) -> Dict[str, Any]:
    """Restore from a backup file"""
    config_path = request.app.state.config_path
    filepath = os.path.join(_get_backup_dir(config_path), filename)

    if not os.path.exists(filepath) or not filename.endswith(".zip"):
        raise HTTPException(status_code=404, detail="Backup not found")

    device_manager = request.app.state.device_manager
    eep_manager = request.app.state.eep_manager

    imported = {
        "devices": False,
        "mappings": False,
        "mapping_overrides": False,
        "custom_profiles": 0,
        "eep_xml": False,
    }

    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            for name in zf.namelist():
                if name in ("devices.json", "devices.yaml"):
                    # Restore devices (support both old JSON and new YAML backups)
                    raw = zf.read(name)
                    if name.endswith(".json"):
                        devices_data = json.loads(raw)
                    else:
                        devices_data = yaml.safe_load(raw) or {}
                    devices_file = os.path.join(config_path, "devices.yaml")
                    async with aiofiles.open(devices_file, 'w') as f:
                        await f.write(yaml.dump(devices_data, default_flow_style=False, allow_unicode=True))
                    imported["devices"] = True
                    if device_manager:
                        await device_manager.load_devices()

                elif name == "mapping.yaml":
                    data = zf.read(name)
                    async with aiofiles.open(os.path.join(config_path, "mapping.yaml"), 'wb') as f:
                        await f.write(data)
                    imported["mappings"] = True

                elif name.startswith("custom_eep/") and name.endswith(".yaml"):
                    data = zf.read(name)
                    custom_path = os.path.join(config_path, "custom_eep")
                    os.makedirs(custom_path, exist_ok=True)
                    async with aiofiles.open(os.path.join(custom_path, os.path.basename(name)), 'wb') as f:
                        await f.write(data)
                    imported["custom_profiles"] += 1

                elif name == "EEP.xml":
                    data = zf.read(name)
                    async with aiofiles.open(os.path.join(config_path, "EEP.xml"), 'wb') as f:
                        await f.write(data)
                    imported["eep_xml"] = True

                elif name in ("mapping_overrides.json", "mapping_overrides.yaml"):
                    # Restore overrides (support both old JSON and new YAML backups)
                    raw = zf.read(name)
                    if name.endswith(".json"):
                        overrides_data = json.loads(raw)
                    else:
                        overrides_data = yaml.safe_load(raw) or {}
                    overrides_path = os.path.join(config_path, "mapping_overrides.yaml")
                    async with aiofiles.open(overrides_path, 'w') as f:
                        await f.write(yaml.dump(overrides_data, default_flow_style=False, allow_unicode=True))
                    imported["mapping_overrides"] = True

        # Reinitialize EEP manager if any EEP-related data was restored
        if eep_manager and (imported.get("eep_xml") or imported.get("custom_profiles", 0) > 0):
            eep_manager.profiles.clear()
            await eep_manager.initialize()

        # Reload mapping overrides into cache after restore
        if imported.get("mapping_overrides") and eep_manager:
            await eep_manager._load_overrides()

        return {"status": "restored", "details": imported}

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Corrupt backup file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")


@router.delete("/backup/{filename}")
async def delete_backup(filename: str, request: Request) -> Dict[str, str]:
    """Delete a backup file"""
    config_path = request.app.state.config_path
    filepath = os.path.join(_get_backup_dir(config_path), filename)

    if not os.path.exists(filepath) or not filename.endswith(".zip"):
        raise HTTPException(status_code=404, detail="Backup not found")

    os.remove(filepath)
    return {"status": "deleted"}


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


@router.get("/download-eep")
async def download_eep(request: Request):
    """Download the currently active EEP.xml (user-uploaded or bundled).

    Companion to /upload-eep: lets users grab the active profile database
    to inspect or edit it before re-uploading.
    """
    config_path = request.app.state.config_path

    user_eep = os.path.join(config_path, "EEP.xml")
    bundled_eep = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "EEP.xml"
    )

    if os.path.exists(user_eep):
        return FileResponse(user_eep, filename="EEP.xml", media_type="application/xml")
    if os.path.exists(bundled_eep):
        return FileResponse(bundled_eep, filename="EEP.xml", media_type="application/xml")
    raise HTTPException(status_code=404, detail="No EEP.xml found")


# === MQTT configuration via Web UI ===
# The HA add-on Configuration tab renders these options too, but offers no
# per-section reset. These endpoints read/write the same /data/options.json
# the Supervisor uses, so both editors stay in sync. Changes take effect on
# the next add-on restart (run.sh re-reads the options with priority
# mqtt.host set -> external broker, empty -> Supervisor auto-discovery).
# Idea from arno0392's fork, adapted to our option key names.

MQTT_DEFAULTS = {
    "host": "",
    "port": 1883,
    "username": "",
    "password": "",
    "discovery_prefix": "homeassistant",
    "prefix": "enoceanmqtt",
    "client_id": "enocean_gateway",
}

_PASSWORD_MASK = "********"


def _options_file() -> str:
    return "/data/options.json"


def _read_options() -> Dict[str, Any]:
    path = _options_file()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write_options(data: Dict[str, Any]) -> None:
    """Atomically write options.json, keeping a .bak of the previous file."""
    path = _options_file()
    tmp = path + ".tmp"
    # Validate serializability before touching anything
    payload = json.dumps(data, indent=2)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                prev = f.read()
            with open(path + ".bak", "w", encoding="utf-8") as f:
                f.write(prev)
        except Exception:
            pass  # backup is best-effort
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp, path)


@router.get("/mqtt-config")
async def get_mqtt_config() -> Dict[str, Any]:
    """Get MQTT options as saved in /data/options.json (password masked)."""
    options = _read_options()
    mqtt = options.get("mqtt") or {}

    merged = dict(MQTT_DEFAULTS)
    for key in MQTT_DEFAULTS:
        if key in mqtt and mqtt[key] is not None:
            merged[key] = mqtt[key]

    password_set = bool(merged.get("password"))
    merged["password"] = _PASSWORD_MASK if password_set else ""

    return {
        "mqtt": merged,
        "password_set": password_set,
        "defaults": {**MQTT_DEFAULTS, "password": ""},
        "note": "Changes apply after the add-on restarts. Empty host = "
                "use Home Assistant's MQTT broker (auto-discovery).",
    }


@router.post("/mqtt-config")
async def save_mqtt_config(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """Save MQTT options to /data/options.json.

    Body: {mqtt: {host, port, username, password, discovery_prefix, prefix,
    client_id}, reset: bool, restart: bool}
    - reset=true ignores mqtt and restores MQTT_DEFAULTS.
    - password equal to the mask sentinel keeps the stored password.
    - restart=true asks the Supervisor to restart this add-on so the new
      settings take effect immediately.
    """
    reset = bool(payload.get("reset"))
    incoming = payload.get("mqtt") or {}

    options = _read_options()
    current = options.get("mqtt") or {}

    if reset:
        new_mqtt = dict(MQTT_DEFAULTS)
    else:
        new_mqtt = dict(MQTT_DEFAULTS)
        new_mqtt.update({k: v for k, v in current.items() if k in MQTT_DEFAULTS})
        for key in MQTT_DEFAULTS:
            if key in incoming and incoming[key] is not None:
                new_mqtt[key] = incoming[key]
        # Mask sentinel means "keep existing password"
        if new_mqtt.get("password") == _PASSWORD_MASK:
            new_mqtt["password"] = current.get("password", "")

    # Basic validation
    try:
        new_mqtt["port"] = int(new_mqtt.get("port") or 1883)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="port must be a number")
    if not (1 <= new_mqtt["port"] <= 65535):
        raise HTTPException(status_code=400, detail="port must be 1-65535")
    for key in ("host", "username", "password", "discovery_prefix", "prefix", "client_id"):
        if not isinstance(new_mqtt.get(key), str):
            raise HTTPException(status_code=400, detail=f"{key} must be a string")
    if not new_mqtt["discovery_prefix"] or not new_mqtt["prefix"] or not new_mqtt["client_id"]:
        raise HTTPException(
            status_code=400,
            detail="discovery_prefix, prefix and client_id must not be empty"
        )

    options["mqtt"] = new_mqtt
    try:
        _write_options(options)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write options: {e}")

    restarting = False
    if payload.get("restart"):
        restarting = await _supervisor_self_restart()

    return {
        "status": "reset" if reset else "saved",
        "restarting": restarting,
        "restart_required": not restarting,
    }


async def _supervisor_self_restart() -> bool:
    """Ask the Supervisor to restart this add-on (needs hassio_api: true)."""
    import asyncio
    import urllib.request

    token = os.getenv("SUPERVISOR_TOKEN", "")
    if not token:
        return False

    def _call():
        req = urllib.request.Request(
            "http://supervisor/addons/self/restart",
            method="POST",
            headers={"Authorization": f"Bearer {token}"},
            data=b"",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _call)
    except Exception:
        return False
