"""
Cardiology Specialty Agent for CareFlow Orchestrator.

Analyses cardiovascular risk factors and produces structured cardiology
findings using Gemini 2.5 Pro.
"""

import json
from typing import List, Optional

from backend.agents.base import SpecialtyAgentBase, SpecialtyAgentError
from backend.schemas import SpecialtyFindings
from backend.services.gemini import GeminiService, GeminiServiceError


class CardiologyAgent(SpecialtyAgentBase):
    """Specialty Agent for cardiology analysis.

    Analyses cardiovascular risk factors (e.g. ECG findings, cardiac
    biomarkers, hypertension, arrhythmias) and returns structured
    cardiology findings.

    Requirements: 3.3, 3.5
    """

    specialty: str = "cardiology"

    def __init__(self, gemini_service: Optional[GeminiService] = None) -> None:
        """Initialise the Cardiology Agent.

        Args:
            gemini_service: An optional pre-configured :class:`GeminiService`
                instance.  When *None* a new instance is created using the
                ``GEMINI_API_KEY`` environment variable.
        """
        self._gemini = gemini_service or GeminiService()

    def analyze(self, case_summary: str, guidelines: List[str]) -> SpecialtyFindings:
        """Analyse cardiovascular risk factors for the given case.

        Args:
            case_summary: Plain-text summary of the patient case.
            guidelines: Cardiology-specific clinical guidelines.

        Returns:
            :class:`~backend.schemas.SpecialtyFindings` with specialty
            ``"cardiology"``, a summary string, and a list of action items.

        Raises:
            SpecialtyAgentError: On Gemini API failure or malformed response.
        """
        guidelines_text = "\n".join(f"- {g}" for g in guidelines) if guidelines else "None provided."

        prompt = (
            "You are an expert cardiologist reviewing a clinical case.\n\n"
            "## Case Summary\n"
            f"{case_summary}\n\n"
            "## Cardiology Guidelines\n"
            f"{guidelines_text}\n\n"
            "## Instructions\n"
            "Analyse the case from a cardiology perspective. Focus on cardiovascular risk "
            "factors, ECG findings, cardiac biomarkers, blood pressure management, "
            "arrhythmias, and any urgent cardiac interventions required.\n\n"
            "Respond with ONLY a valid JSON object in the following format (no markdown, no extra text):\n"
            "{\n"
            '  "specialty": "cardiology",\n'
            '  "summary": "<concise cardiology summary>",\n'
            '  "action_items": ["<action 1>", "<action 2>", ...]\n'
            "}"
        )

        try:
            raw_response = self._gemini.generate(prompt)
        except GeminiServiceError as exc:
            raise SpecialtyAgentError(
                specialty=self.specialty,
                detail=str(exc.detail),
            ) from exc

        return self._parse_response(raw_response)

    def _parse_response(self, raw: str) -> SpecialtyFindings:
        """Parse and validate the Gemini JSON response.

        Args:
            raw: Raw text returned by Gemini.

        Returns:
            A validated :class:`~backend.schemas.SpecialtyFindings` instance.

        Raises:
            SpecialtyAgentError: If the JSON is malformed or required fields
                are missing.
        """
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SpecialtyAgentError(
                specialty=self.specialty,
                detail=f"Failed to parse JSON response: {exc}",
            ) from exc

        missing = [f for f in ("specialty", "summary", "action_items") if f not in data]
        if missing:
            raise SpecialtyAgentError(
                specialty=self.specialty,
                detail=f"Response missing required fields: {missing}",
            )

        return SpecialtyFindings(
            specialty=data["specialty"],
            summary=data["summary"],
            action_items=data["action_items"],
        )
