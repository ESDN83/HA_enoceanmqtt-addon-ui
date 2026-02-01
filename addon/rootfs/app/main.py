from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from lxml import etree
import requests
import yaml
import os
from pydantic import BaseModel
from typing import Dict, List, Optional

app = FastAPI()
templates = Jinja2Templates(directory="templates")

CONFIG_DIR = os.getenv("CONFIG_DIR", "/config")  # Mounted in HA, or local for testing

class Device(BaseModel):
    name: str
    address: str
    rorg: str
    func: str
    type: str
    sender_id: Optional[str] = None

class Mapping(BaseModel):
    eep: str
    components: Dict[str, Dict]

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/eeps")
async def get_eeps():
    try:
        # Download EEP.xml from EnOcean Alliance
        url = "https://www.enocean-alliance.org/wp-content/uploads/2020/08/EEP.xml"
        response = requests.get(url)
        response.raise_for_status()
        root = etree.fromstring(response.content)

        eeps = {}
        for profile in root.findall(".//profile"):
            rorg = profile.find("rorg").text
            func = profile.find("func").text
            type_ = profile.find("type").text
            key = f"{rorg}-{func}-{type_}"
            description = profile.find("description").text if profile.find("description") is not None else ""
            eeps[key] = {
                "rorg": rorg,
                "func": func,
                "type": type_,
                "description": description,
                "fields": []  # TODO: Parse telegram fields from XML
            }
        return eeps
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load EEPs: {str(e)}")

@app.get("/api/devices")
async def get_devices():
    try:
        devices_file = os.path.join(CONFIG_DIR, "enoceanmqtt.devices")
        if os.path.exists(devices_file):
            with open(devices_file, "r") as f:
                content = f.read()
                # Parse INI-like format or YAML
                # For simplicity, return as text or parse
                return {"content": content}
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/devices")
async def update_devices(devices: Dict[str, Device]):
    try:
        devices_file = os.path.join(CONFIG_DIR, "enoceanmqtt.devices")
        # Convert to INI format
        content = ""
        for name, dev in devices.items():
            content += f"[{name}]\n"
            content += f"address = {dev.address}\n"
            content += f"rorg = {dev.rorg}\n"
            content += f"func = {dev.func}\n"
            content += f"type = {dev.type}\n"
            if dev.sender_id:
                content += f"sender_id = {dev.sender_id}\n"
            content += "\n"
        with open(devices_file, "w") as f:
            f.write(content)
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mappings")
async def get_mappings():
    try:
        mappings_file = os.path.join(CONFIG_DIR, "mapping.yaml")
        if os.path.exists(mappings_file):
            with open(mappings_file, "r") as f:
                data = yaml.safe_load(f)
                return data or {}
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mappings")
async def update_mappings(mappings: Dict):
    try:
        mappings_file = os.path.join(CONFIG_DIR, "mapping.yaml")
        with open(mappings_file, "w") as f:
            yaml.dump(mappings, f)
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/validate")
async def validate_config(file: UploadFile = File(...)):
    try:
        content = await file.read()
        # Validate YAML
        data = yaml.safe_load(content)
        # TODO: Add EEP validation logic
        return {"valid": True, "errors": []}
    except yaml.YAMLError as e:
        return {"valid": False, "errors": [str(e)]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/wizards/{device_type}")
async def get_wizard(device_type: str):
    # Pre-defined templates
    wizards = {
        "eltako_tf61j": {
            "eep": "A5-3F-7F",
            "description": "Eltako TF61J Jalousie Actor",
            "config": {
                "address": "0xFF8CE888",
                "rorg": "0xA5",
                "func": "0x3F",
                "type": "0x7F"
            }
        },
        "kessel_staufix": {
            "eep": "A5-20-04",
            "description": "Kessel Stauffix Valve",
            "config": {
                "address": "0x01234567",
                "rorg": "0xA5",
                "func": "0x20",
                "type": "0x04"
            }
        }
    }
    if device_type in wizards:
        return wizards[device_type]
    raise HTTPException(status_code=404, detail="Wizard not found")

@app.get("/api/export/{type}")
async def export_config(type: str):
    if type == "devices":
        file_path = os.path.join(CONFIG_DIR, "enoceanmqtt.devices")
    elif type == "mappings":
        file_path = os.path.join(CONFIG_DIR, "mapping.yaml")
    else:
        raise HTTPException(status_code=400, detail="Invalid type")
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/octet-stream', filename=f"{type}.yaml" if type == "mappings" else f"{type}.ini")
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/api/import")
async def import_config(file: UploadFile = File(...)):
    try:
        content = await file.read()
        # Determine type from filename or content
        if file.filename.endswith(".yaml"):
            data = yaml.safe_load(content)
            # Assume mappings
            mappings_file = os.path.join(CONFIG_DIR, "mapping.yaml")
            with open(mappings_file, "w") as f:
                yaml.dump(data, f)
        else:
            # Assume devices
            devices_file = os.path.join(CONFIG_DIR, "enoceanmqtt.devices")
            with open(devices_file, "w") as f:
                f.write(content.decode())
        return {"status": "imported"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
