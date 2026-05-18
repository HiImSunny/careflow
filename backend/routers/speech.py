"""
Speech router — WebSocket endpoint for real-time audio transcription.

Accepts an audio stream via WebSocket upgrade and streams transcription
results back to the client using the SpeechmaticsService.  Works in both
real (Speechmatics API) and mock modes.

Endpoint:
    WS /api/speech/transcribe
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.speechmatics import SpeechmaticsError, SpeechmaticsService

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: wrap WebSocket receive loop as an async iterator of bytes
# ---------------------------------------------------------------------------


async def _ws_audio_chunks(websocket: WebSocket) -> AsyncIterator[bytes]:
    """Yield raw audio bytes received from the WebSocket client.

    Stops when the client disconnects or sends a text ``"stop"`` message.
    """
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes"):
                yield message["bytes"]
            elif message.get("text") == "stop":
                # Client signals end of audio stream
                break
    except WebSocketDisconnect:
        return


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/speech/transcribe")
async def transcribe_audio(websocket: WebSocket) -> None:
    """Stream audio from the client and return real-time transcription.

    Protocol:
        1. Client connects via WebSocket.
        2. Client sends raw audio bytes (PCM 16 kHz f32le recommended).
        3. Server streams back transcription text frames as plain strings.
        4. Client sends text ``"stop"`` or disconnects to end the session.
        5. Server sends ``{"type": "done"}`` JSON frame and closes.

    Error handling:
        - On SpeechmaticsError, the server sends ``{"type": "error", "detail": "..."}``
          and closes the connection with code 1011.
        - On unexpected disconnect, the session is cleaned up silently.
    """
    await websocket.accept()
    logger.info("Speech WebSocket connection accepted.")

    service = SpeechmaticsService()

    try:
        audio_stream = _ws_audio_chunks(websocket)

        async for transcript_chunk in service.transcribe_stream(audio_stream):
            # Send each partial transcript as a plain text frame
            await websocket.send_text(transcript_chunk)

        # Signal completion
        await websocket.send_json({"type": "done"})
        await websocket.close()
        logger.info("Speech WebSocket session completed successfully.")

    except SpeechmaticsError as exc:
        logger.error("Speechmatics error during transcription: %s", exc)
        try:
            await websocket.send_json({"type": "error", "detail": exc.detail})
            await websocket.close(code=1011)
        except Exception:
            pass  # Connection may already be closed

    except WebSocketDisconnect:
        logger.info("Speech WebSocket client disconnected.")

    except Exception as exc:
        logger.exception("Unexpected error in speech WebSocket: %s", exc)
        try:
            await websocket.send_json(
                {"type": "error", "detail": f"Internal server error: {exc}"}
            )
            await websocket.close(code=1011)
        except Exception:
            pass
