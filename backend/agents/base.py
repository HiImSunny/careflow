"""
Base class and shared error type for all Specialty Agents.
"""

from abc import ABC, abstractmethod
from typing import List

from backend.schemas import SpecialtyFindings


class SpecialtyAgentError(Exception):
    """Raised when a Specialty Agent encounters an error during analysis.

    Attributes:
        specialty: The name of the specialty agent that failed.
        detail: A human-readable description of the failure.
    """

    def __init__(self, specialty: str, detail: str) -> None:
        super().__init__(f"{specialty} agent error: {detail}")
        self.specialty = specialty
        self.detail = detail


class SpecialtyAgentBase(ABC):
    """Abstract base class for all Specialty Agents.

    Subclasses must declare a ``specialty`` class attribute and implement
    the ``analyze`` method.
    """

    specialty: str

    @abstractmethod
    def analyze(self, case_summary: str, guidelines: List[str]) -> SpecialtyFindings:
        """Analyse a clinical case from this specialty's perspective.

        Args:
            case_summary: A plain-text summary of the patient case produced
                by the Orchestrator Agent.
            guidelines: A list of specialty-specific clinical guideline strings
                loaded from ``data/guidelines.json``.

        Returns:
            A :class:`~backend.schemas.SpecialtyFindings` instance containing
            the specialty name, a summary string, and a list of action items.

        Raises:
            SpecialtyAgentError: If the Gemini API call fails or the response
                cannot be parsed into the expected structure.
        """
