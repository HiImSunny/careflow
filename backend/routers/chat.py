"""
Router for GET /api/chat/{case_id} — streams agent messages via Server-Sent Events.

Agent messages are published to an in-memory asyncio.Queue keyed by case_id
during orchestration. This endpoint reads from that queue and streams each
message as an SSE event to the connected client.

Requirements: 5.1, 5.3, 5.4
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Dict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory event queues — keyed by case_id
# ---------------------------------------------------------------------------

# Each value is a list of asyncio.Queue instances (one per connected SSE client).
# Using a list allows multiple simultaneous clients for the same case_id.
_queues: Dict[str, list[asyncio.Queue]] = {}


def get_or_create_queue(case_id: str) -> asyncio.Queue:
    """Create and register a new queue for the given case_id.

    Returns the newly created queue so the caller can subscribe to it.
    """
    queue: asyncio.Queue = asyncio.Queue()
    if case_id not in _queues:
        _queues[case_id] = []
    _queues[case_id].append(queue)
    return queue


def remove_queue(case_id: str, queue: asyncio.Queue) -> None:
    """Remove a queue from the registry when the client disconnects."""
    if case_id in _queues:
        try:
            _queues[case_id].remove(queue)
        except ValueError:
            pass
        if not _queues[case_id]:
            del _queues[case_id]


def publish_agent_message(case_id: str, message: dict) -> None:
    """Publish an agent message to all queues registered for case_id.

    This function is called from synchronous orchestration code (crew.py).
    It uses ``asyncio.get_event_loop()`` to schedule the put on the running
    event loop, making it safe to call from a thread pool executor.

    Args:
        case_id: The case identifier.
        message: A dict with keys ``agent``, ``content``, ``timestamp``.
    """
    if case_id not in _queues:
        return

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No running event loop — messages cannot be delivered.
        logger.warning(
            "No running event loop; cannot publish agent message for case_id=%s", case_id
        )
        return

    for queue in list(_queues.get(case_id, [])):
        if loop.is_running():
            loop.call_soon_threadsafe(queue.put_nowait, message)
        else:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Queue full for case_id=%s — dropping message.", case_id)


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------

_SENTINEL = object()  # signals end-of-stream


async def _event_generator(case_id: str) -> AsyncIterator[str]:
    """Yield SSE-formatted strings from the queue for case_id.

    Yields messages until a ``None`` sentinel is received (orchestration done)
    or the client disconnects.
    """
    queue = get_or_create_queue(case_id)
    try:
        while True:
            try:
                # Poll with a short timeout so we can detect client disconnects.
                message = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                # Send a keep-alive comment to prevent proxy timeouts.
                yield ": keep-alive\n\n"
                continue

            if message is None:
                # Sentinel — orchestration complete.
                completion_event = {
                    "agent": "system",
                    "content": "Care plan ready",
                    "timestamp": _utc_now(),
                    "type": "complete",
                }
                yield f"data: {json.dumps(completion_event)}\n\n"
                break

            yield f"data: {json.dumps(message)}\n\n"
    finally:
        remove_queue(case_id, queue)


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@router.get("/chat/{case_id}")
async def chat_stream(case_id: str) -> StreamingResponse:
    """Stream agent messages for a given case as Server-Sent Events.

    The client should open an ``EventSource`` to this endpoint.  Each event
    carries a JSON-encoded ``AgentMessage`` in the ``data`` field.  A final
    event with ``type: "complete"`` is sent when orchestration finishes.

    Requirements: 5.1, 5.3, 5.4
    """
    return StreamingResponse(
        _event_generator(case_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
