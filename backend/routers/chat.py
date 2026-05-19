"""
Router for GET /api/chat/{case_id} — streams agent messages via Server-Sent Events.

Agent messages are published to an in-memory store keyed by case_id during
orchestration. This endpoint replays any already-received messages immediately
on connect, then streams new ones as they arrive.

Requirements: 5.1, 5.3, 5.4
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Main event loop reference — captured at startup so worker threads can use it
# ---------------------------------------------------------------------------

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store a reference to the main asyncio event loop.
    Called from app startup so ThreadPoolExecutor workers can publish messages.
    """
    global _main_loop
    _main_loop = loop

# ---------------------------------------------------------------------------
# In-memory message store — keyed by case_id
# ---------------------------------------------------------------------------

# Stores all messages published for a case so late-connecting clients get them.
_message_history: Dict[str, List[dict]] = {}

# Whether orchestration is complete for a case_id (sentinel received).
_completed: Dict[str, bool] = {}

# Live subscriber queues — one per connected SSE client.
_queues: Dict[str, List[asyncio.Queue]] = {}

# Max messages to keep per case (prevents unbounded memory growth).
_MAX_HISTORY = 200


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_or_create_queue(case_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _queues.setdefault(case_id, []).append(queue)
    return queue


def remove_queue(case_id: str, queue: asyncio.Queue) -> None:
    if case_id in _queues:
        try:
            _queues[case_id].remove(queue)
        except ValueError:
            pass
        if not _queues[case_id]:
            del _queues[case_id]


def publish_agent_message(case_id: str, message: Optional[dict]) -> None:
    """Publish an agent message (or None sentinel for completion).

    Called from synchronous orchestration code via ThreadPoolExecutor.
    Stores the message in history and fans out to all live subscribers.
    """
    if message is None:
        # Sentinel — mark orchestration complete and notify subscribers.
        _completed[case_id] = True
        loop = _main_loop
        if loop and loop.is_running():
            for queue in list(_queues.get(case_id, [])):
                loop.call_soon_threadsafe(queue.put_nowait, None)
        return

    # Store in history (capped).
    history = _message_history.setdefault(case_id, [])
    if len(history) < _MAX_HISTORY:
        history.append(message)

    # Fan out to live subscribers.
    loop = _main_loop
    if loop and loop.is_running():
        for queue in list(_queues.get(case_id, [])):
            loop.call_soon_threadsafe(queue.put_nowait, message)
    else:
        logger.warning(
            "No running event loop; cannot publish message for case_id=%s", case_id
        )


# ---------------------------------------------------------------------------
# SSE event generator
# ---------------------------------------------------------------------------

async def _event_generator(case_id: str) -> AsyncIterator[str]:
    """Yield SSE-formatted strings for the given case_id.

    1. Immediately replays all historical messages for this case.
    2. If orchestration is already complete, sends the completion event and exits.
    3. Otherwise subscribes to live updates and streams until completion.
    """
    # 1. Replay history
    for msg in list(_message_history.get(case_id, [])):
        yield f"data: {json.dumps(msg)}\n\n"

    # 2. Already done — send completion and exit
    if _completed.get(case_id):
        completion = {
            "agent": "system",
            "content": "Care plan ready",
            "timestamp": _utc_now(),
            "type": "complete",
        }
        yield f"data: {json.dumps(completion)}\n\n"
        return

    # 3. Subscribe to live updates
    queue = get_or_create_queue(case_id)
    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue

            if message is None:
                # Orchestration complete
                completion = {
                    "agent": "system",
                    "content": "Care plan ready",
                    "timestamp": _utc_now(),
                    "type": "complete",
                }
                yield f"data: {json.dumps(completion)}\n\n"
                break

            yield f"data: {json.dumps(message)}\n\n"
    finally:
        remove_queue(case_id, queue)


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------

@router.get("/chat/{case_id}")
async def chat_stream(case_id: str) -> StreamingResponse:
    """Stream agent messages for a given case as Server-Sent Events.

    Replays historical messages immediately on connect, then streams live
    updates. Sends a final ``type: complete`` event when orchestration finishes.

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
