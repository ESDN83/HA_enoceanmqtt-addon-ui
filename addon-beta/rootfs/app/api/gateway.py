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


class TeachInResult(BaseModel):
    """Teach-in result"""
    sender_id: str
    rorg: str
    func: str
    type: str
    dbm: int


class ActorTeachInRequest(BaseModel):
    """Request to send teach-in to an actuator"""
    destination: str  # Target actuator address (hex, e.g. "0x05834FA4")
    sender_offset: int = 1  # Offset from base ID (1-127)
    # "switch"/"cover" -> F6 rocker, "light" -> A5-38-08,
    # "cover_gfvs" -> A5-3F-7F, the Eltako shutter command path (#40)
    actuator_type: str = "switch"
    repeats: int = 4  # cover_gfvs only: how often the sequence is repeated


class RepeatTeachInRequest(BaseModel):
    """Request to send teach-in repeatedly for 30 seconds"""
    destination: str  # Target actuator address (hex)
    sender_offset: int = 1
    actuator_type: str = "switch"
    duration_seconds: int = 30
    interval_seconds: float = 5.0


class TestActuatorRequest(BaseModel):
    """Request to test an actuator with F6 rocker command"""
    device_name: str
    command: str  # "ON", "OFF", "OPEN", "CLOSE", "STOP"


@router.get("/info")
async def get_gateway_info(request: Request) -> Dict[str, Any]:
    """Get EnOcean gateway information including base ID"""
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
        "base_id": serial_handler.base_id
    }


@router.post("/read-base-id")
async def read_base_id(request: Request) -> Dict[str, Any]:
    """Read the base ID from the EnOcean USB transceiver"""
    serial_handler = request.app.state.serial_handler

    if not serial_handler or not serial_handler.is_connected:
        raise HTTPException(status_code=503, detail="EnOcean gateway not connected")

    base_id = await serial_handler.read_base_id()
    if not base_id:
        raise HTTPException(status_code=500, detail="Failed to read base ID from transceiver")

    return {"base_id": base_id}


@router.post("/teach-in-actuator")
async def teach_in_actuator(req: ActorTeachInRequest, request: Request) -> Dict[str, Any]:
    """Send teach-in telegram to an Eltako actuator.

    The actuator must be in learn mode before calling this endpoint.
    - Dimmers (actuator_type="light"): sends A5-38-08 (4BS Central Command) teach-in
    - Shutters (actuator_type="cover_gfvs"): sends the Eltako GFVS teach-in,
      A5-3F-7F, which is what lets the shutter be driven to a position (#40)
    - Switches/covers: sends F6 (RPS) rocker press+release teach-in
    """
    serial_handler = request.app.state.serial_handler

    if not serial_handler or not serial_handler.is_connected:
        raise HTTPException(status_code=503, detail="EnOcean gateway not connected")

    if not serial_handler.base_id:
        raise HTTPException(status_code=400, detail="Base ID not available. Try reading it first via /read-base-id")

    if not 1 <= req.sender_offset <= 127:
        raise HTTPException(status_code=400, detail="sender_offset must be between 1 and 127")

    # Parse destination address
    try:
        dest = int(req.destination.replace("0x", "").replace("0X", ""), 16)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid destination address: {req.destination}")

    sender_id = serial_handler.get_sender_id(req.sender_offset)

    # Dimmers use A5-38-08 (4BS Central Command) teach-in
    if req.actuator_type == "light":
        success = await serial_handler.send_a5_teach_in(dest, req.sender_offset)
        teach_type = "A5-38-08 (Central Command Dimming)"
    elif req.actuator_type == "cover_gfvs":
        # Teaching GFVS locks the actuator's learn mode afterwards. That is
        # the actuator's own behaviour, not something this endpoint can
        # undo, so the dialog warns about it.
        rounds = max(1, min(int(req.repeats or 1), 10))
        success = await serial_handler.send_a5_3f_teach_in(
            dest, req.sender_offset, repeats=rounds
        )
        plural = "round" if rounds == 1 else "rounds"
        teach_type = f"A5-3F-7F (Eltako GFVS, {rounds} {plural})"
    else:
        success = await serial_handler.send_f6_teach_in(dest, req.sender_offset)
        teach_type = "F6 (RPS Rocker)"

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send teach-in telegram")

    return {
        "status": "sent",
        "destination": req.destination,
        "sender_id": f"0x{sender_id:08X}",
        "sender_offset": req.sender_offset,
        "teach_type": teach_type,
        "message": f"Teach-in telegram sent ({teach_type}). If actuator was in learn mode, it should now respond to this sender ID."
    }


@router.post("/teach-in-repeat")
async def teach_in_repeat(req: RepeatTeachInRequest, request: Request) -> Dict[str, Any]:
    """Send teach-in telegram repeatedly for a duration.

    Useful when the actuator needs to be close to the USB300 and the user
    needs time to put it into learn mode while telegrams are being sent.
    Sends teach-in every interval_seconds for duration_seconds.
    """
    serial_handler = request.app.state.serial_handler

    if not serial_handler or not serial_handler.is_connected:
        raise HTTPException(status_code=503, detail="EnOcean gateway not connected")

    if not serial_handler.base_id:
        raise HTTPException(status_code=400, detail="Base ID not available. Try reading it first via /read-base-id")

    if not 1 <= req.sender_offset <= 127:
        raise HTTPException(status_code=400, detail="sender_offset must be between 1 and 127")

    try:
        dest = int(req.destination.replace("0x", "").replace("0X", ""), 16)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid destination address: {req.destination}")

    sender_id = serial_handler.get_sender_id(req.sender_offset)
    duration = min(req.duration_seconds, 60)  # Max 60 seconds
    interval = max(req.interval_seconds, 2.0)  # Min 2 seconds between sends

    rounds = int(duration / interval)
    sent_count = 0

    logger.info(f"=== REPEAT TEACH-IN START === {rounds} rounds, every {interval}s")

    for i in range(rounds):
        if req.actuator_type == "light":
            await serial_handler.send_a5_teach_in(dest, req.sender_offset)
        elif req.actuator_type == "cover_gfvs":
            # One sequence per round here, the rounds are the repetition.
            await serial_handler.send_a5_3f_teach_in(dest, req.sender_offset, repeats=1)
        else:
            await serial_handler.send_f6_teach_in(dest, req.sender_offset)
        sent_count += 1
        logger.info(f"  Repeat teach-in round {i+1}/{rounds} sent")

        if i < rounds - 1:
            await asyncio.sleep(interval)

    teach_type = {"light": "A5-38-08 (Dimmer)",
                  "cover_gfvs": "A5-3F-7F (Eltako GFVS)"}.get(
                      req.actuator_type, "F6 (Switch/Cover)")
    logger.info(f"=== REPEAT TEACH-IN COMPLETE === {sent_count} rounds sent")

    return {
        "status": "sent",
        "rounds_sent": sent_count,
        "duration_seconds": duration,
        "destination": req.destination,
        "sender_id": f"0x{sender_id:08X}",
        "teach_type": teach_type,
        "message": f"Sent {sent_count} teach-in rounds over {duration}s. Check if actuator confirmed (lamp blinks)."
    }


@router.post("/test-actuator")
async def test_actuator(req: TestActuatorRequest, request: Request) -> Dict[str, Any]:
    """Send a command to an actuator from the UI, without going through HA.

    The command takes exactly the same route as one arriving over MQTT: the
    queue, then `_handle_device_command`. This endpoint used to carry its own
    copy of the rocker and dimmer semantics, which is how its stop button kept
    sending a bare release long after the MQTT path had stopped doing that,
    and how it stayed blind to the direction a shutter last ran in (#39). One
    behaviour, one place, as ADR-0003 and ADR-0012 intend.
    """
    serial_handler = request.app.state.serial_handler
    device_manager = request.app.state.device_manager

    if not serial_handler or not serial_handler.is_connected:
        raise HTTPException(status_code=503, detail="EnOcean gateway not connected")

    if not device_manager:
        raise HTTPException(status_code=500, detail="Device manager not initialized")

    device = device_manager.get_device(req.device_name)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{req.device_name}' not found")

    if not device.actuator_type:
        raise HTTPException(status_code=400, detail="Device is not configured as an actuator")

    if not device.sender_id:
        raise HTTPException(status_code=400, detail="Device has no sender_id configured")

    command = req.command.strip().upper()
    allowed = {"light": ("ON", "OFF"), "switch": ("ON", "OFF"),
               "cover": ("OPEN", "CLOSE", "STOP")}.get(device.actuator_type, ())
    if command not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown command '{command}' for a {device.actuator_type}. Use {', '.join(allowed)}."
        )

    # A test of a dimmer should be visible, so ON asks for full brightness
    # rather than the value the actuator happens to have stored. The command
    # handler reads a bare number as a brightness percentage.
    payload = "100" if (command == "ON" and device.actuator_type == "light"
                        and device.rorg.upper() != "F6") else command

    submit = getattr(request.app.state, "submit_command", None)
    if submit is None:
        # No MQTT broker means no queue. Fall back to the handler itself, so
        # the test button still works on a gateway-only setup.
        submit = getattr(request.app.state, "handle_device_command", None)
    if submit is None:
        raise HTTPException(status_code=503, detail="Command handling not initialised")

    logger.info(f"Test actuator: {req.device_name} ({device.actuator_type}) = {command}")
    await submit(req.device_name, payload)

    return {
        "status": "queued",
        "device": req.device_name,
        "command": command,
        "sender_id": device.sender_id,
        "destination": device.address
    }


@router.websocket("/teach-in")
async def teach_in_websocket(websocket: WebSocket):
    """WebSocket endpoint for teach-in mode"""
    await websocket.accept()

    session_id = str(id(websocket))
    active_teach_in_sessions[session_id] = websocket
    serial_handler = None

    logger.info(f"Teach-in session started: {session_id}")

    try:
        # Get serial handler from app state via websocket.app
        serial_handler = websocket.app.state.serial_handler

        if not serial_handler or not serial_handler.is_connected:
            await websocket.send_json({
                "type": "error",
                "message": "EnOcean gateway not connected"
            })
            return

        # Set up teach-in callback
        async def on_teach_in(data: Dict[str, Any]):
            if session_id in active_teach_in_sessions:
                try:
                    await active_teach_in_sessions[session_id].send_json({
                        "type": "teach_in",
                        "data": data
                    })
                    logger.info(f"Teach-in data sent to WebSocket: {data}")
                except Exception as e:
                    logger.error(f"Failed to send teach-in to WebSocket: {e}")

        serial_handler.set_teach_in_callback(on_teach_in)

        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "message": "Press the teach-in button on your EnOcean device"
        })
        logger.info("Teach-in mode active - waiting for device telegrams...")

        # Keep connection open and handle messages
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=60.0  # 60 second timeout
                )

                if message.get("type") == "stop":
                    logger.info("Teach-in stopped by user")
                    break

            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        logger.info(f"Teach-in session disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Teach-in session error: {e}", exc_info=True)
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
    """Get list of unknown devices that have sent telegrams (excludes configured devices)"""
    telegram_buffer = request.app.state.telegram_buffer if request else None

    if not telegram_buffer:
        return []

    unknown = telegram_buffer.get_unknown_devices()

    # Filter out devices that are already configured
    device_manager = getattr(request.app.state, 'device_manager', None)
    if device_manager:
        configured_addresses = set()
        for device in device_manager.devices.values():
            addr = device.address.upper().replace("0X", "0x")
            configured_addresses.add(addr)
            # Also add without 0x prefix
            configured_addresses.add(addr.replace("0x", ""))

        unknown = [
            d for d in unknown
            if d["sender_id"].upper().replace("0X", "0x") not in configured_addresses
            and d["sender_id"].upper().replace("0x", "").replace("0X", "") not in configured_addresses
        ]

    return unknown


@router.post("/clear-telegrams")
async def clear_telegrams(request: Request) -> Dict[str, Any]:
    """Clear all stored telegrams and unknown devices"""
    telegram_buffer = request.app.state.telegram_buffer if request else None

    if not telegram_buffer:
        return {"status": "no buffer"}

    telegram_buffer.clear()
    return {"status": "cleared"}


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
