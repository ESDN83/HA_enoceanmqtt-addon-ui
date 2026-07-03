"""
EEP API - EnOcean Equipment Profile operations
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter()


class CustomProfileCreate(BaseModel):
    """Custom profile creation model"""
    rorg: str
    func: str
    type: str
    description: str
    fields: List[Dict[str, Any]] = []
    ha_mapping: Optional[Dict[str, Dict[str, Any]]] = None


@router.get("")
async def list_profiles(request: Request) -> List[Dict[str, Any]]:
    """Get all EEP profiles"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    return eep_manager.get_all_profiles()


@router.get("/tree")
async def get_profile_tree(request: Request) -> Dict[str, Any]:
    """Get profiles organized as a tree structure by RORG/FUNC/TYPE"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    tree = {}
    overrides = await eep_manager.get_all_mapping_overrides()

    # Track which override keys are matched to existing profiles
    matched_override_keys = set()

    for profile in eep_manager.profiles.values():
        if profile.rorg not in tree:
            tree[profile.rorg] = {
                "rorg": profile.rorg,
                "description": _get_rorg_description(profile.rorg),
                "funcs": {}
            }

        if profile.func not in tree[profile.rorg]["funcs"]:
            tree[profile.rorg]["funcs"][profile.func] = {
                "func": profile.func,
                "description": "",
                "types": {}
            }

        eep_upper = profile.eep_id.upper()
        if eep_upper in overrides:
            matched_override_keys.add(eep_upper)

        tree[profile.rorg]["funcs"][profile.func]["types"][profile.type] = {
            "type": profile.type,
            "eep_id": profile.eep_id,
            "description": profile.description,
            "is_custom": profile.is_custom,
            "has_mapping_override": eep_upper in overrides
        }

    # Find orphaned overrides (keys in mapping_overrides.json that don't match any loaded profile)
    orphaned = []
    for key in overrides:
        if key not in matched_override_keys:
            orphaned.append({"eep_id": key, "mapping": overrides[key]})

    return {"tree": tree, "orphaned_overrides": orphaned}


@router.get("/search/{query}")
async def search_profiles(query: str, request: Request) -> List[Dict[str, Any]]:
    """Search EEP profiles"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    results = eep_manager.search_profiles(query)
    return [p.to_dict() for p in results]


@router.get("/rorg/{rorg}")
async def get_profiles_by_rorg(rorg: str, request: Request) -> List[Dict[str, Any]]:
    """Get profiles by RORG"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    results = eep_manager.get_profiles_by_rorg(rorg)
    return [p.to_dict() for p in results]


@router.get("/{eep_id}")
async def get_profile(eep_id: str, request: Request) -> Dict[str, Any]:
    """Get a specific EEP profile, including any mapping override"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    profile = eep_manager.get_profile(eep_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{eep_id}' not found")

    result = profile.to_dict()

    # Include mapping override info for non-custom profiles
    if not profile.is_custom:
        override = await eep_manager.get_mapping_override(eep_id)
        if override:
            result["mapping_override"] = override
            result["has_mapping_override"] = True
        else:
            result["has_mapping_override"] = False

    return result


@router.get("/{eep_id}/mapping")
async def get_profile_mapping(eep_id: str, request: Request) -> Dict[str, Any]:
    """Get the effective HA mapping for a profile (override or default)"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    profile = eep_manager.get_profile(eep_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{eep_id}' not found")

    override = await eep_manager.get_mapping_override(eep_id)

    return {
        "eep_id": eep_id.upper(),
        "mapping": override if override else profile.ha_mapping,
        "is_override": override is not None,
        "is_custom_profile": profile.is_custom,
    }


@router.put("/{eep_id}/mapping")
async def save_profile_mapping(eep_id: str, request: Request) -> Dict[str, Any]:
    """Save a mapping override for any EEP profile"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    profile = eep_manager.get_profile(eep_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{eep_id}' not found")

    body = await request.json()

    # For custom profiles, save directly into the profile
    if profile.is_custom:
        profile_data = {
            "rorg": profile.rorg,
            "func": profile.func,
            "type": profile.type,
            "description": profile.description,
            "fields": profile.fields,
        }
        success = await eep_manager.save_custom_profile(profile_data, ha_mapping=body)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save")
        return {"status": "saved", "is_override": False}

    # For standard profiles, save as an override
    success = await eep_manager.save_mapping_override(eep_id, body)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save mapping override")

    return {"status": "saved", "is_override": True}


@router.delete("/{eep_id}/mapping")
async def delete_profile_mapping(eep_id: str, request: Request) -> Dict[str, Any]:
    """Delete mapping override for a standard profile (revert to EEP.xml default)"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    profile = eep_manager.get_profile(eep_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{eep_id}' not found")

    if profile.is_custom:
        # For custom profiles, clear the ha_mapping
        profile_data = {
            "rorg": profile.rorg,
            "func": profile.func,
            "type": profile.type,
            "description": profile.description,
            "fields": profile.fields,
        }
        await eep_manager.save_custom_profile(profile_data, ha_mapping={})
        return {"status": "cleared"}

    success = await eep_manager.delete_mapping_override(eep_id)
    if not success:
        raise HTTPException(status_code=404, detail="No mapping override found")

    return {"status": "deleted"}


@router.post("/custom")
async def create_custom_profile(profile: CustomProfileCreate, request: Request) -> Dict[str, Any]:
    """Create a custom EEP profile"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    # Validate required fields are not empty
    if not profile.rorg.strip() or not profile.func.strip() or not profile.type.strip():
        raise HTTPException(status_code=400, detail="RORG, FUNC, and TYPE are required")
    if not profile.description.strip():
        raise HTTPException(status_code=400, detail="Description is required")

    profile_data = {
        "rorg": profile.rorg.strip().upper().replace("0X", ""),
        "func": profile.func.strip().upper().replace("0X", "").zfill(2),
        "type": profile.type.strip().upper().replace("0X", "").zfill(2),
        "description": profile.description.strip(),
        "fields": profile.fields
    }

    try:
        success = await eep_manager.save_custom_profile(profile_data, ha_mapping=profile.ha_mapping)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to write custom profile to disk")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create custom profile: {str(e)}")

    eep_id = f"{profile_data['rorg']}-{profile_data['func']}-{profile_data['type']}"
    new_profile = eep_manager.get_profile(eep_id)

    return {"status": "created", "profile": new_profile.to_dict() if new_profile else profile_data}


@router.put("/custom/{eep_id}")
async def update_custom_profile(eep_id: str, profile: CustomProfileCreate, request: Request) -> Dict[str, Any]:
    """Update a custom EEP profile"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    existing = eep_manager.get_profile(eep_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Profile '{eep_id}' not found")

    if not existing.is_custom:
        raise HTTPException(status_code=400, detail="Cannot modify built-in profile")

    profile_data = {
        "rorg": profile.rorg.upper().replace("0X", ""),
        "func": profile.func.upper().replace("0X", "").zfill(2),
        "type": profile.type.upper().replace("0X", "").zfill(2),
        "description": profile.description,
        "fields": profile.fields
    }

    success = await eep_manager.save_custom_profile(profile_data, ha_mapping=profile.ha_mapping)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update custom profile")

    updated = eep_manager.get_profile(eep_id)
    return {"status": "updated", "profile": updated.to_dict() if updated else profile_data}


@router.delete("/custom/{eep_id}")
async def delete_custom_profile(eep_id: str, request: Request) -> Dict[str, str]:
    """Delete a custom EEP profile"""
    eep_manager = request.app.state.eep_manager
    if not eep_manager:
        raise HTTPException(status_code=500, detail="EEP manager not initialized")

    existing = eep_manager.get_profile(eep_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Profile '{eep_id}' not found")

    if not existing.is_custom:
        raise HTTPException(status_code=400, detail="Cannot delete built-in profile")

    success = await eep_manager.delete_custom_profile(eep_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete custom profile")

    return {"status": "deleted"}


def _get_rorg_description(rorg: str) -> str:
    """Get description for RORG"""
    descriptions = {
        "F6": "RPS Telegram (Rocker Switch)",
        "D5": "1BS Telegram (1 Byte Sensor)",
        "A5": "4BS Telegram (4 Byte Sensor)",
        "D2": "VLD Telegram (Variable Length Data)",
        "D0": "Signal Telegram",
        "D1": "MSC Telegram",
        "D4": "UTE Telegram",
    }
    return descriptions.get(rorg.upper(), f"RORG {rorg}")
