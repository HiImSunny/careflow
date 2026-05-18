"""
Gemini 2.5 Pro service client for CareFlow Orchestrator.

Wraps the google-generativeai SDK to support text-only and multimodal
(text + image) requests. Loads the API key from the environment via
python-dotenv.
"""

import base64
import os
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()


class GeminiServiceError(Exception):
    """Raised when the Gemini API returns an error or an unexpected response."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Gemini API error: {detail}")
        self.detail = detail


class GeminiService:
    """Client wrapper for the Gemini 2.5 Pro generative model.

    Supports text-only and multimodal (text + base64-encoded image) requests.
    The API key is read from the ``GEMINI_API_KEY`` environment variable unless
    an explicit key is passed to the constructor.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialise the Gemini client.

        Args:
            api_key: Gemini API key.  When *None* the value is read from the
                ``GEMINI_API_KEY`` environment variable.

        Raises:
            GeminiServiceError: If no API key can be found.
        """
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        if not resolved_key:
            raise GeminiServiceError(
                "GEMINI_API_KEY is not set. "
                "Provide it as an argument or set the environment variable."
            )

        genai.configure(api_key=resolved_key)
        # Use model name from env var GEMINI_MODEL, defaulting to gemini-2.0-flash
        # which has a much higher free-tier quota than gemini-2.5-pro.
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self._model = genai.GenerativeModel(model_name)

    def generate(self, prompt: str, image_b64: Optional[str] = None) -> str:
        """Generate a text response from Gemini 2.5 Pro.

        When *image_b64* is provided the request is sent as a multimodal
        content list containing the image bytes followed by the text prompt.

        Args:
            prompt: The text prompt to send to the model.
            image_b64: Optional base64-encoded JPEG image.

        Returns:
            The model's text response as a plain string.

        Raises:
            GeminiServiceError: On any API-level failure.
        """
        try:
            if image_b64:
                image_bytes = base64.b64decode(image_b64)
                content = [
                    {
                        "mime_type": "image/jpeg",
                        "data": image_bytes,
                    },
                    prompt,
                ]
            else:
                content = prompt

            response = self._model.generate_content(content)
            return response.text

        except GeminiServiceError:
            # Re-raise our own errors without wrapping them again.
            raise
        except Exception as exc:
            raise GeminiServiceError(str(exc)) from exc
