"""
Speechmatics real-time speech-to-text service for CareFlow Orchestrator.

Streams audio chunks to the Speechmatics API via WebSocket and yields
partial transcription results.  When the Speechmatics SDK is not installed
or the API key is not configured, the service falls back to a mock
implementation that returns canned transcription text — useful for local
development and demos.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import AsyncIterator, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class SpeechmaticsError(Exception):
    """Raised when the Speechmatics service fails to connect or transcribe."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Speechmatics error: {detail}")
        self.detail = detail


# ---------------------------------------------------------------------------
# SDK availability check
# ---------------------------------------------------------------------------

_SDK_AVAILABLE = False
try:
    import speechmatics  # noqa: F401

    _SDK_AVAILABLE = True
    logger.info("Speechmatics SDK detected — real transcription enabled.")
except ImportError:
    logger.warning(
        "speechmatics-python SDK not installed. "
        "SpeechmaticsService will use mock transcription."
    )


# ---------------------------------------------------------------------------
# Service implementation
# ---------------------------------------------------------------------------


class SpeechmaticsService:
    """WebSocket client for Speechmatics real-time transcription.

    When the SDK is available and ``SPEECHMATICS_API_KEY`` is set, audio
    chunks are forwarded to the Speechmatics RT API and partial transcripts
    are yielded as they arrive.

    When the SDK is unavailable or the key is missing, a mock implementation
    is used that echoes a placeholder transcript — allowing the WebSocket
    endpoint to function end-to-end without a real API key.
    """

    # Speechmatics RT API endpoint
    _RT_URL = "wss://eu2.rt.speechmatics.com/v2"

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialise the service.

        Args:
            api_key: Speechmatics API key.  When *None* the value is read from
                the ``SPEECHMATICS_API_KEY`` environment variable.
        """
        self._api_key: Optional[str] = api_key or os.getenv("SPEECHMATICS_API_KEY")
        self._use_mock = not _SDK_AVAILABLE or not self._api_key

        if self._use_mock:
            reason = (
                "SDK not installed"
                if not _SDK_AVAILABLE
                else "SPEECHMATICS_API_KEY not set"
            )
            logger.info(
                "SpeechmaticsService running in MOCK mode (%s). "
                "Transcription results will be simulated.",
                reason,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """Stream audio chunks and yield partial transcription results.

        Args:
            audio_chunks: An async iterator that yields raw PCM/audio bytes.

        Yields:
            Partial transcription strings as they become available.

        Raises:
            SpeechmaticsError: On connection failure (real mode only).
        """
        if self._use_mock:
            async for transcript in self._mock_transcribe(audio_chunks):
                yield transcript
        else:
            async for transcript in self._real_transcribe(audio_chunks):
                yield transcript

    # ------------------------------------------------------------------
    # Real implementation (Speechmatics SDK)
    # ------------------------------------------------------------------

    async def _real_transcribe(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """Transcribe using the Speechmatics Python SDK.

        Uses the SDK's ``WebsocketClient`` to open a real-time session,
        forwards audio chunks, and yields transcript text from
        ``AddTranscript`` messages.

        Raises:
            SpeechmaticsError: On connection or transcription failure.
        """
        try:
            import speechmatics
            from speechmatics.models import (
                AudioSettings,
                ConnectionSettings,
                TranscriptionConfig,
            )

            results: asyncio.Queue[Optional[str]] = asyncio.Queue()

            def on_transcript(msg: dict) -> None:
                """Callback invoked for each AddTranscript event."""
                text = msg.get("metadata", {}).get("transcript", "")
                if text:
                    results.put_nowait(text)

            settings = ConnectionSettings(
                url=self._RT_URL,
                auth_token=self._api_key,
            )
            audio_settings = AudioSettings(
                encoding="pcm_f32le",
                sample_rate=16000,
                chunk_size=1024,
            )
            transcription_config = TranscriptionConfig(
                language="en",
                enable_partials=True,
            )

            client = speechmatics.WebsocketClient(settings)
            client.add_event_handler(
                speechmatics.models.ServerMessageType.AddTranscript,
                on_transcript,
            )

            async def _feed_audio() -> None:
                async for chunk in audio_chunks:
                    await client.send_audio(chunk)
                await client.end_stream()

            async def _run_session() -> None:
                await client.run(
                    audio_settings=audio_settings,
                    transcription_config=transcription_config,
                )
                results.put_nowait(None)  # sentinel

            feed_task = asyncio.create_task(_feed_audio())
            session_task = asyncio.create_task(_run_session())

            while True:
                item = await results.get()
                if item is None:
                    break
                yield item

            await asyncio.gather(feed_task, session_task)

        except SpeechmaticsError:
            raise
        except Exception as exc:
            raise SpeechmaticsError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Mock implementation
    # ------------------------------------------------------------------

    async def _mock_transcribe(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """Consume audio chunks and yield simulated transcription results.

        Drains the audio stream and emits a series of canned partial
        transcripts to simulate real-time speech recognition.  This allows
        the WebSocket endpoint to work end-to-end without a real API key.
        """
        mock_phrases = [
            "Patient presents with ",
            "chest pain and shortness of breath. ",
            "History of hypertension ",
            "and type 2 diabetes. ",
            "Requesting cardiology and radiology review.",
        ]

        chunk_count = 0
        async for _ in audio_chunks:
            chunk_count += 1
            # Emit a mock phrase roughly every 5 chunks to simulate streaming
            if chunk_count % 5 == 0:
                phrase_index = (chunk_count // 5 - 1) % len(mock_phrases)
                await asyncio.sleep(0.05)  # simulate network latency
                yield mock_phrases[phrase_index]

        # Emit any remaining phrases after the stream ends
        if chunk_count == 0:
            # No audio received — yield a placeholder
            yield "[No audio received — mock transcription]"
        else:
            # Yield a completion marker
            yield " [Transcription complete]"
