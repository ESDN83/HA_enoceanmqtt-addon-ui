"""
Gateway API - EnOcean gateway operations (teach-in, send commands)
"""

import asyncio
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Store active teach-in sessions
active_teach_in_sessions: Dict[str, WebSocket] = {}


class SendCommandRequest(BaseModel):
    """Request to send an EnOcean command"""
    device_name: str
    command: str
    value: Optional[Any] = None


class TeachInResult(BaseModel):
    """Teach-in result"""
    sender_id: str
    rorg: str
    func: str
    type: str
    dbm: int


@router.get("/info")
async def get_gateway_info(request: Request) -> Dict[str, Any]:
    """Get EnOcean gateway information"""
    serial_handler = request.app.state.serial_handler

    if not serial_handler or not serial_handler.is_connected:
        return {
            "connected": False,
            "port": "",
            "base_id": None
        }

    return {
        "connected": True,
        "port": serial_handler.port,
        "is_tcp": serial_handler.is_tcp,
        "base_id": None  # TODO: Implement base ID retrieval
    }


@router.post("/send")
async def send_command(cmd: SendCommandRequest, request: Request) -> Dict[str, Any]:
    """Send a command to an EnOcean device"""
    serial_handler = request.app.state.serial_handler
    device_manager = request.app.state.device_manager
    eep_manager = request.app.state.eep_manager

    if not serial_handler or not serial_handler.is_connected:
        raise HTTPException(status_code=503, detail="EnOcean gateway not connected")

    if not device_manager:
        raise HTTPException(status_code=500, detail="Device manager not initialized")

    # Get device
    device = device_manager.get_device(cmd.device_name)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{cmd.device_name}' not found")

    if not device.sender_id:
        raise HTTPException(status_code=400, detail="Device has no sender_id configured")

    # Get EEP profile
    profile = eep_manager.get_profile(device.eep_id) if eep_manager else None

    # Build and send telegram based on command
    # This is a simplified implementation - real implementation would need to
    # properly encode the command based on EEP profile
    try:
        rorg = int(device.rorg, 16)
        sender_id = int(device.sender_id.replace("0x", "").replace("0X", ""), 16)
        destination = int(device.address.replace("0x", "").replace("0X", ""), 16)

        # Build data based on command type
        # This is placeholder logic - real implementation depends on device type
        if cmd.command == "on":
            data = bytes([0x01, 0x00, 0x00, 0x09])  # Example: switch on
        elif cmd.command == "off":
            data = bytes([0x00, 0x00, 0x00, 0x08])  # Example: switch off
        elif cmd.command == "dim":
            level = int(cmd.value or 100)
            data = bytes([0x02, level, 0x00, 0x09])  # Example: dim
        elif cmd.command == "stop":
            data = bytes([0x00, 0x00, 0x00, 0x08])  # Example: stop
        else:
            raise HTTPException(status_code=400, detail=f"Unknown command: {cmd.command}")

        success = await serial_handler.send_telegram(
            sender_id=sender_id,
            rorg=rorg,
            data=data,
            destination=destination
        )

        if success:
            return {"status": "sent", "device": cmd.device_name, "command": cmd.command}
        else:
            raise HTTPException(status_code=500, detail="Failed to send telegram")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid device configuration: {e}")
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send command: {e}")


@router.websocket("/teach-in")
async def teach_in_websocket(websocket: WebSocket, request: Request = None):
    """WebSocket endpoint for teach-in mode"""
    await websocket.accept()

    session_id = str(id(websocket))
    active_teach_in_sessions[session_id] = websocket

    logger.info(f"Teach-in session started: {session_id}")

    try:
        # Get serial handler
        serial_handler = request.app.state.serial_handler if request else None

        if not serial_handler or not serial_handler.is_connected:
            await websocket.send_json({
                "type": "error",
                "message": "EnOcean gateway not connected"
            })
            return

        # Set up teach-in callback
        async def on_teach_in(data: Dict[str, Any]):
            if session_id in active_teach_in_sessions:
                await active_teach_in_sessions[session_id].send_json({
                    "type": "teach_in",
                    "data": data
                })

        serial_handler.set_teach_in_callback(on_teach_in)

        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "message": "Press the teach-in button on your EnOcean device"
        })

        # Keep connection open and handle messages
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=60.0  # 60 second timeout
                )

                if message.get("type") == "stop":
                    break

            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        logger.info(f"Teach-in session disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Teach-in session error: {e}")
    finally:
        # Clean up
        if session_id in active_teach_in_sessions:
            del active_teach_in_sessions[session_id]

        # Remove callback
        if serial_handler:
            serial_handler.set_teach_in_callback(None)

        logger.info(f"Teach-in session ended: {session_id}")


@router.get("/recent-telegrams")
async def get_recent_telegrams(limit: int = 50, request: Request = None) -> List[Dict[str, Any]]:
    """Get recent received telegrams (for debugging)"""
    telegram_buffer = request.app.state.telegram_buffer if request else None

    if not telegram_buffer:
        return []

    return telegram_buffer.get_recent(limit)


@router.get("/unknown-devices")
async def get_unknown_devices(request: Request) -> List[Dict[str, Any]]:
    """Get list of unknown devices that have sent telegrams"""
    telegram_buffer = request.app.state.telegram_buffer if request else None

    if not telegram_buffer:
        return []

    return telegram_buffer.get_unknown_devices()


@router.get("/telegram-stats")
async def get_telegram_stats(request: Request) -> Dict[str, Any]:
    """Get telegram buffer statistics"""
    telegram_buffer = request.app.state.telegram_buffer if request else None

    if not telegram_buffer:
        return {"total_count": 0, "max_size": 0, "unknown_device_count": 0}

    return telegram_buffer.get_stats()


@router.post("/test-connection")
async def test_connection(request: Request) -> Dict[str, Any]:
    """Test EnOcean gateway connection"""
    serial_handler = request.app.state.serial_handler

    if not serial_handler:
        return {
            "success": False,
            "error": "Serial handler not initialized"
        }

    if not serial_handler.is_connected:
        try:
            await serial_handler.connect()
            return {
                "success": True,
                "message": "Connection successful"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    return {
        "success": True,
        "message": "Already connected"
    }
