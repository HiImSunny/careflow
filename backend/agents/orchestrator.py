"""
Orchestrator Agent for CareFlow.

Uses Gemini 2.5 Pro to decompose a clinical case into relevant specialties,
a structured summary, and key findings.

Validates: Requirements 2.1, 2.3
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from backend.services.gemini import GeminiService, GeminiServiceError

# The only specialties the system supports.
VALID_SPECIALTIES: List[str] = ["radiology", "oncology", "cardiology", "pharmacy"]


class OrchestratorError(Exception):
    """Raised when the Orchestrator Agent cannot parse or produce a valid result."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Orchestrator error: {detail}")
        self.detail = detail


@dataclass
class DecomposedCase:
    """Structured output produced by the Orchestrator Agent.

    Attributes:
        specialties:   List of relevant medical specialties (subset of
                       VALID_SPECIALTIES) identified for this case.
        summary:       A concise clinical summary of the case.
        key_findings:  A list of the most important clinical observations.
    """

    specialties: List[str] = field(default_factory=list)
    summary: str = ""
    key_findings: List[str] = field(default_factory=list)


_SYSTEM_PROMPT = """\
You are a senior clinical decision-support AI. Your task is to analyse the
provided patient case and return a structured JSON object — nothing else.

The JSON object MUST have exactly these three keys:

  "specialties"   – a JSON array of strings, each being one or more of the
                    following values (use only these exact strings):
                    "radiology", "oncology", "cardiology", "pharmacy"
                    Include only the specialties that are clinically relevant
                    to this case.  The array must contain at least one value.

  "summary"       – a single string: a concise (2–4 sentence) clinical
                    summary of the case.

  "key_findings"  – a JSON array of strings, each describing one important
                    clinical observation or finding from the case.

Do NOT include any text outside the JSON object.  Do NOT wrap the JSON in
markdown code fences.  Return only the raw JSON.
"""


class OrchestratorAgent:
    """Decomposes a clinical case into specialties, summary, and key findings.

    Uses the Gemini 2.5 Pro model via :class:`GeminiService`.

    Args:
        gemini_service: An initialised :class:`GeminiService` instance.
                        When *None* a new instance is created using the
                        ``GEMINI_API_KEY`` environment variable.
    """

    def __init__(self, gemini_service: Optional[GeminiService] = None) -> None:
        self._gemini = gemini_service or GeminiService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decompose(self, text: str, image_b64: Optional[str] = None) -> DecomposedCase:
        """Decompose a clinical case into structured components.

        Args:
            text:       The clinical case text (notes, history, etc.).
            image_b64:  Optional base64-encoded JPEG image (e.g. a scan).

        Returns:
            A :class:`DecomposedCase` with validated specialties, a summary,
            and key findings.

        Raises:
            OrchestratorError: If the Gemini response cannot be parsed as
                               valid JSON or is missing required fields.
            GeminiServiceError: If the Gemini API call itself fails.
        """
        prompt = self._build_prompt(text)

        try:
            raw_response = self._gemini.generate(prompt, image_b64)
        except GeminiServiceError:
            raise  # Let the caller handle upstream API errors.

        return self._parse_response(raw_response)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, text: str) -> str:
        """Combine the system instructions with the case text."""
        return f"{_SYSTEM_PROMPT}\n\n--- PATIENT CASE ---\n{text}\n--- END OF CASE ---"

    def _parse_response(self, raw: str) -> DecomposedCase:
        """Parse and validate the JSON response from Gemini.

        Args:
            raw: The raw string returned by the Gemini model.

        Returns:
            A validated :class:`DecomposedCase`.

        Raises:
            OrchestratorError: On malformed JSON or missing/invalid fields.
        """
        # Strip optional markdown code fences that the model may add despite
        # instructions (e.g. ```json ... ```).
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise OrchestratorError(
                f"Gemini returned malformed JSON: {exc}. Raw response: {raw!r}"
            ) from exc

        if not isinstance(data, dict):
            raise OrchestratorError(
                f"Expected a JSON object, got {type(data).__name__}. "
                f"Raw response: {raw!r}"
            )

        # Validate required keys.
        for key in ("specialties", "summary", "key_findings"):
            if key not in data:
                raise OrchestratorError(
                    f"Missing required key '{key}' in Gemini response. "
                    f"Raw response: {raw!r}"
                )

        specialties = data["specialties"]
        summary = data["summary"]
        key_findings = data["key_findings"]

        if not isinstance(specialties, list):
            raise OrchestratorError(
                f"'specialties' must be a list, got {type(specialties).__name__}."
            )
        if not isinstance(summary, str):
            raise OrchestratorError(
                f"'summary' must be a string, got {type(summary).__name__}."
            )
        if not isinstance(key_findings, list):
            raise OrchestratorError(
                f"'key_findings' must be a list, got {type(key_findings).__name__}."
            )

        # Filter specialties to only valid values (case-insensitive, then
        # normalised to lowercase).
        filtered_specialties: List[str] = []
        for s in specialties:
            if isinstance(s, str) and s.lower() in VALID_SPECIALTIES:
                filtered_specialties.append(s.lower())

        # Deduplicate while preserving order.
        seen: set = set()
        unique_specialties: List[str] = []
        for s in filtered_specialties:
            if s not in seen:
                seen.add(s)
                unique_specialties.append(s)

        # Ensure key_findings contains only strings.
        string_findings: List[str] = [
            str(f) for f in key_findings if f is not None
        ]

        return DecomposedCase(
            specialties=unique_specialties,
            summary=str(summary),
            key_findings=string_findings,
        )
