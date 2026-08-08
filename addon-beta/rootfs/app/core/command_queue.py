"""Inbound command queue.

Home Assistant delivers a scene as a burst of MQTT messages, and every command
ends in one or more radio telegrams. The transceiver has a single radio and a
small transmit queue, so the fire-and-forget dispatch this replaces overran it:
telegrams were silently dropped while the optimistic state echo still went out,
and Home Assistant showed devices as switched that never heard anything. Below
roughly 300 ms between commands it became unreliable.

The queue makes bursts survivable without pretending the radio is parallel:

- Commands are processed by a small pool of workers instead of one task per
  message, so a slow command cannot multiply into a stampede.
- Two commands for the same device keep the order they arrived in.
- Every command has a deadline. A stalled one is abandoned and the queue moves
  on, it can never park the whole send path. The press/release pair inside the
  serial handler is shielded, so a deadline can never abandon a press and
  leave a shutter running.
- A full queue is logged, loudly. Silent loss was the original complaint.

See ADR-0012.
"""

import time
import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Two workers, because the transmit slot serializes the radio anyway. The
# second one is there so a command stuck before the slot (a device lock, a
# dying transport) does not add its latency to everything behind it.
WORKERS = 2

# A burst of a few dozen commands is normal, thousands are a runaway
# automation. Bound the queue so it cannot eat memory, and say so when it
# overflows instead of dropping in silence.
MAX_PENDING = 200
BACKLOG_WARN = 25
BACKLOG_WARN_INTERVAL = 10.0

# Worst case for one command: acquiring the transmit slot (up to 1s) plus a
# press/release pair with two stalled writes. Anything beyond that is not slow,
# it is stuck.
COMMAND_TIMEOUT = 2.0


@dataclass
class _Command:
    device: str
    payload: str
    entity: Optional[str]
    queued_at: float

    def __str__(self) -> str:
        target = f"{self.device}/{self.entity}" if self.entity else self.device
        return f"'{self.payload}' for {target}"


class CommandQueue:
    """Serializes inbound device commands onto a worker pool."""

    def __init__(self,
                 handler: Callable[[str, str, Optional[str]], Awaitable[None]],
                 workers: int = WORKERS,
                 maxsize: int = MAX_PENDING,
                 timeout: float = COMMAND_TIMEOUT):
        self._handler = handler
        self._worker_count = workers
        self._timeout = timeout
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        # One lock per device keeps ON from overtaking OFF. asyncio.Queue.get()
        # and Lock.acquire() are both FIFO, so the order Home Assistant sent
        # survives even when two workers pick up the same device.
        self._locks: Dict[str, asyncio.Lock] = {}
        self._workers: List[asyncio.Task] = []
        self._dropped = 0
        self._timed_out = 0
        self._last_backlog_warn = 0.0

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def timed_out(self) -> int:
        return self._timed_out

    async def start(self):
        if self._workers:
            return
        self._workers = [
            asyncio.create_task(self._worker(i), name=f"command-worker-{i}")
            for i in range(self._worker_count)
        ]
        logger.info(f"Command queue started with {self._worker_count} workers")

    async def stop(self):
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._workers = []
        self._locks.clear()

    async def submit(self, device_name: str, payload: str, entity: str = None):
        """Queue one command.

        Awaited on the event loop from the MQTT callback thread, so it must not
        block: an overflowing queue drops the command and logs it rather than
        applying backpressure to the MQTT client.
        """
        command = _Command(device_name, payload, entity, time.monotonic())
        try:
            self._queue.put_nowait(command)
        except asyncio.QueueFull:
            self._dropped += 1
            logger.error(
                f"Command queue full ({self._queue.maxsize} pending), dropped "
                f"{command}, {self._dropped} dropped in total"
            )
            return

        depth = self._queue.qsize()
        now = time.monotonic()
        if depth >= BACKLOG_WARN and now - self._last_backlog_warn > BACKLOG_WARN_INTERVAL:
            self._last_backlog_warn = now
            logger.warning(
                f"Command queue backlog: {depth} pending, commands are arriving "
                f"faster than the transceiver can send them"
            )

    async def _worker(self, index: int):
        while True:
            command = await self._queue.get()
            try:
                lock = self._locks.setdefault(command.device, asyncio.Lock())
                async with lock:
                    waited = time.monotonic() - command.queued_at
                    if waited > 1.0:
                        logger.debug(f"Command {command} waited {waited * 1000:.0f} ms in queue")
                    await asyncio.wait_for(
                        self._handler(command.device, command.payload, command.entity),
                        timeout=self._timeout
                    )
            except asyncio.TimeoutError:
                self._timed_out += 1
                logger.error(
                    f"Command {command} timed out after {self._timeout:.0f}s, "
                    f"giving up on it and continuing with the queue"
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Command {command} failed: {e}", exc_info=True)
            finally:
                self._queue.task_done()
