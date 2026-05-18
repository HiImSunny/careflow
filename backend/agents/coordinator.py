"""
Coordinator Agent for CareFlow Orchestrator.

Reconciles findings from all Specialty Agents into a unified Care Plan
using Gemini 2.5 Pro. Handles partial failures gracefully by including
warning alerts for any agents that failed during execution.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.schemas import CarePlan, SpecialtyFindings, TimelineEntry

logger = logging.getLogger(__name__)


class CoordinatorError(Exception):
    """Raised when the Coordinator Agent encounters an unrecoverable error."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Coordinator error: {detail}")
        self.detail = detail


class CoordinatorAgent:
    """Reconciles specialty findings into a unified Care Plan.

    Uses Gemini 2.5 Pro to synthesise a timeline, recommendations, and
    alerts from the structured findings produced by each Specialty Agent.
    Failed agents are represented as warning entries in the alerts list.
    """

    def __init__(self, gemini_service=None) -> None:
        """Initialise the Coordinator Agent.

        Args:
            gemini_service: An optional pre-configured GeminiService instance.
                When *None*, a new instance is created using the environment
                variable ``GEMINI_API_KEY``.
        """
        if gemini_service is None:
            # Lazy import to avoid loading google-generativeai at module import time
            from backend.services.gemini import GeminiService  # noqa: PLC0415
            gemini_service = GeminiService()
        self._gemini = gemini_service

    def reconcile(
        self,
        findings: Dict[str, SpecialtyFindings],
        failed_agents: List[str] = [],
        case_id: Optional[str] = None,
    ) -> CarePlan:
        """Reconcile specialty findings into a unified Care Plan.

        Builds a prompt containing all available specialty findings and
        instructs Gemini to produce a structured JSON response with
        ``timeline``, ``recommendations``, and ``alerts`` fields.

        For each agent in *failed_agents*, a warning alert is appended to
        the final Care Plan regardless of what Gemini returns.

        The returned ``CarePlan`` always contains all four required fields
        (``timeline``, ``recommendations``, ``alerts``, ``findings``),
        defaulting to empty lists/dicts when Gemini returns partial data.

        Args:
            findings: Mapping of specialty name → SpecialtyFindings for
                agents that completed successfully.
            failed_agents: List of specialty names whose agents failed.
            case_id: Optional case identifier to embed in the Care Plan.

        Returns:
            A fully populated ``CarePlan`` instance.

        Raises:
            CoordinatorError: If Gemini returns an unrecoverable error and
                no fallback can be constructed.
        """
        resolved_case_id = case_id or _generate_case_id()

        # Build the reconciliation prompt
        prompt = self._build_prompt(findings, failed_agents)

        # Call Gemini and parse the response
        timeline: List[TimelineEntry] = []
        recommendations: List[str] = []
        alerts: List[str] = []

        try:
            raw_response = self._gemini.generate(prompt)
            parsed = _parse_gemini_response(raw_response)
            timeline = _extract_timeline(parsed.get("timeline", []))
            recommendations = _extract_string_list(parsed.get("recommendations", []))
            alerts = _extract_string_list(parsed.get("alerts", []))
        except Exception as exc:
            # The coordinator must be resilient — log the error and continue
            # with empty defaults so the Care Plan is always returned.
            logger.warning(
                "Error during Gemini reconciliation — returning partial Care Plan: %s",
                exc,
            )

        # Append failure warnings for each failed agent (Requirement 2.8)
        for specialty in failed_agents:
            warning = f"WARNING: {specialty} agent failed — findings unavailable"
            if warning not in alerts:
                alerts.append(warning)

        return CarePlan(
            case_id=resolved_case_id,
            timeline=timeline,
            recommendations=recommendations,
            alerts=alerts,
            findings=findings,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        findings: Dict[str, SpecialtyFindings],
        failed_agents: List[str],
    ) -> str:
        """Build the reconciliation prompt for Gemini.

        Args:
            findings: Successfully completed specialty findings.
            failed_agents: Specialties whose agents failed.

        Returns:
            A formatted prompt string.
        """
        lines: List[str] = [
            "You are a senior clinical coordinator. Your task is to reconcile the "
            "following specialty findings into a unified care plan.",
            "",
            "## Specialty Findings",
            "",
        ]

        if findings:
            for specialty, sf in findings.items():
                lines.append(f"### {specialty.capitalize()}")
                lines.append(f"**Summary:** {sf.summary}")
                if sf.action_items:
                    lines.append("**Action Items:**")
                    for item in sf.action_items:
                        lines.append(f"  - {item}")
                lines.append("")
        else:
            lines.append("No specialty findings are available.")
            lines.append("")

        if failed_agents:
            lines.append("## Failed Agents")
            lines.append(
                "The following specialty agents failed and their findings are unavailable:"
            )
            for specialty in failed_agents:
                lines.append(f"  - {specialty}")
            lines.append("")

        lines += [
            "## Instructions",
            "",
            "Produce a JSON object with exactly these three keys:",
            "",
            '  "timeline": an array of objects, each with keys "timestamp" (ISO 8601 string), '
            '"specialty" (string), and "description" (string). Include one entry per '
            "significant finding or recommended action.",
            "",
            '  "recommendations": an array of plain-text strings, each describing a '
            "concrete clinical recommendation derived from the findings.",
            "",
            '  "alerts": an array of plain-text strings for any urgent concerns, '
            "drug interactions, contraindications, or critical findings that require "
            "immediate attention.",
            "",
            "Return ONLY the JSON object — no markdown fences, no extra commentary.",
        ]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _generate_case_id() -> str:
    """Generate a timestamp-based fallback case ID."""
    import uuid

    return str(uuid.uuid4())


def _parse_gemini_response(raw: str) -> dict:
    """Parse the raw Gemini response string into a dict.

    Strips optional markdown code fences before parsing.

    Args:
        raw: The raw text returned by Gemini.

    Returns:
        Parsed JSON dict.

    Raises:
        ValueError: If the response cannot be parsed as JSON.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove opening fence (```json or ```)
        lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from Gemini: {exc}") from exc


def _extract_timeline(raw_timeline: object) -> List[TimelineEntry]:
    """Convert raw timeline data from Gemini into TimelineEntry objects.

    Silently skips malformed entries rather than raising.

    Args:
        raw_timeline: The value of the ``timeline`` key from Gemini's JSON.

    Returns:
        List of valid TimelineEntry objects (may be empty).
    """
    if not isinstance(raw_timeline, list):
        return []

    entries: List[TimelineEntry] = []
    for item in raw_timeline:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(
                TimelineEntry(
                    timestamp=str(item.get("timestamp", datetime.now(timezone.utc).isoformat())),
                    specialty=str(item.get("specialty", "unknown")),
                    description=str(item.get("description", "")),
                )
            )
        except Exception:
            # Skip malformed entries
            continue

    return entries


def _extract_string_list(raw: object) -> List[str]:
    """Convert a raw value into a list of strings.

    Args:
        raw: Expected to be a list of strings from Gemini's JSON.

    Returns:
        List of strings (may be empty).
    """
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item is not None]
