"""
Orchestration flow for CareFlow Orchestrator.

Provides ``run_orchestration(request, guidelines) -> CarePlan`` which:

1. Uses ``OrchestratorAgent.decompose()`` to identify relevant specialties.
2. Dispatches the identified Specialty Agents in parallel via
   ``concurrent.futures.ThreadPoolExecutor``.
3. Collects ``failed_agents`` for any agent that raises ``SpecialtyAgentError``.
4. Passes successful findings and ``failed_agents`` to
   ``CoordinatorAgent.reconcile()`` and returns the resulting ``CarePlan``.

Validates: Requirements 2.2, 2.8, 5.1, 5.3
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from backend.agents.base import SpecialtyAgentBase, SpecialtyAgentError
from backend.agents.cardiology import CardiologyAgent
from backend.agents.coordinator import CoordinatorAgent
from backend.agents.oncology import OncologyAgent
from backend.agents.orchestrator import OrchestratorAgent
from backend.agents.pharmacy import PharmacyAgent
from backend.agents.radiology import RadiologyAgent
from backend.schemas import CarePlan, OrchestrateRequest, SpecialtyFindings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent message publishing helper
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _emit_agent_message(case_id: Optional[str], agent: str, content: str) -> None:
    """Publish an agent message to the SSE queue for the given case_id.

    Silently no-ops when case_id is None or the chat router is unavailable.

    Requirements: 5.1, 5.3
    """
    if not case_id:
        return
    try:
        from backend.routers.chat import publish_agent_message  # lazy import

        publish_agent_message(
            case_id,
            {
                "agent": agent,
                "content": content,
                "timestamp": _utc_now(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not publish agent message: %s", exc)

# ---------------------------------------------------------------------------
# Agent registry — maps specialty name → agent class
# ---------------------------------------------------------------------------

_AGENT_REGISTRY: Dict[str, type] = {
    "radiology": RadiologyAgent,
    "oncology": OncologyAgent,
    "cardiology": CardiologyAgent,
    "pharmacy": PharmacyAgent,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_orchestration(
    request: OrchestrateRequest,
    guidelines: dict,
    *,
    orchestrator_agent: Optional[OrchestratorAgent] = None,
    coordinator_agent: Optional[CoordinatorAgent] = None,
) -> CarePlan:
    """Run the full multi-agent orchestration pipeline.

    Steps:
    1. Decompose the case with ``OrchestratorAgent`` to identify specialties.
    2. Dispatch the relevant Specialty Agents in parallel (CrewAI if available,
       otherwise ``ThreadPoolExecutor``).
    3. Collect ``failed_agents`` for any agent that raises ``SpecialtyAgentError``.
    4. Reconcile findings with ``CoordinatorAgent`` and return the ``CarePlan``.

    Args:
        request: The incoming orchestration request containing ``text``,
            ``image_b64``, and an optional ``case_id``.
        guidelines: A dict mapping specialty name → list of guideline strings,
            as loaded from ``data/guidelines.json``.
        orchestrator_agent: Optional pre-built ``OrchestratorAgent`` (useful
            for testing / dependency injection).
        coordinator_agent: Optional pre-built ``CoordinatorAgent`` (useful
            for testing / dependency injection).

    Returns:
        A fully populated ``CarePlan``.

    Raises:
        ``OrchestratorError`` / ``GeminiServiceError``: If the decomposition
            step fails (callers should map these to HTTP 502).
    """
    case_id = request.case_id

    # ------------------------------------------------------------------
    # Step 1 — Decompose the case
    # ------------------------------------------------------------------
    _emit_agent_message(case_id, "Orchestrator", "Decomposing case and identifying relevant specialties…")

    orch = orchestrator_agent or OrchestratorAgent()
    decomposed = orch.decompose(
        text=request.text or "",
        image_b64=request.image_b64,
    )

    logger.info(
        "Decomposed case — specialties: %s, summary length: %d chars",
        decomposed.specialties,
        len(decomposed.summary),
    )

    _emit_agent_message(
        case_id,
        "Orchestrator",
        f"Identified specialties: {', '.join(decomposed.specialties) or 'none'}. Dispatching agents…",
    )

    # ------------------------------------------------------------------
    # Step 2 — Build specialty agent instances for identified specialties
    # ------------------------------------------------------------------
    agents: List[SpecialtyAgentBase] = []
    for specialty in decomposed.specialties:
        agent_cls = _AGENT_REGISTRY.get(specialty)
        if agent_cls is None:
            logger.warning("Unknown specialty '%s' — skipping.", specialty)
            continue
        agents.append(agent_cls())  # type: ignore[abstract]

    # ------------------------------------------------------------------
    # Step 3 — Dispatch agents in parallel
    # ------------------------------------------------------------------
    findings: Dict[str, SpecialtyFindings] = {}
    failed_agents: List[str] = []

    if agents:
        findings, failed_agents = _dispatch_agents(
            agents=agents,
            case_summary=decomposed.summary,
            guidelines=guidelines,
            case_id=case_id,
        )
    else:
        logger.warning("No specialty agents identified — proceeding with empty findings.")
        _emit_agent_message(case_id, "Orchestrator", "No specialty agents identified — proceeding with coordinator.")

    # ------------------------------------------------------------------
    # Step 4 — Reconcile findings into a Care Plan
    # ------------------------------------------------------------------
    _emit_agent_message(case_id, "Coordinator", "Reconciling findings from all specialty agents…")

    coord = coordinator_agent or CoordinatorAgent()
    care_plan = coord.reconcile(
        findings=findings,
        failed_agents=failed_agents,
        case_id=request.case_id,
    )

    _emit_agent_message(case_id, "Coordinator", "Care plan reconciliation complete.")

    # Signal orchestration complete (None sentinel closes the SSE stream).
    try:
        from backend.routers.chat import publish_agent_message  # lazy import

        if case_id:
            publish_agent_message(case_id, None)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not send completion sentinel: %s", exc)

    return care_plan


# ---------------------------------------------------------------------------
# Parallel dispatch helpers
# ---------------------------------------------------------------------------


def _dispatch_agents(
    agents: List[SpecialtyAgentBase],
    case_summary: str,
    guidelines: dict,
    case_id: Optional[str] = None,
) -> Tuple[Dict[str, SpecialtyFindings], List[str]]:
    """Dispatch specialty agents in parallel using ThreadPoolExecutor."""
    items = [(agent.specialty, agent) for agent in agents]
    return _run_agents_parallel(items, case_summary, guidelines, case_id=case_id)


def _run_agents_parallel(
    specialty_agent_pairs: List[Tuple[str, SpecialtyAgentBase]],
    case_summary: str,
    guidelines: dict,
    case_id: Optional[str] = None,
) -> Tuple[Dict[str, SpecialtyFindings], List[str]]:
    """Run specialty agents in parallel using ``ThreadPoolExecutor``.

    Each agent's ``analyze()`` call is wrapped in try/except so that a single
    agent failure does not abort the entire pipeline (Requirement 2.8).

    Args:
        specialty_agent_pairs: List of (specialty_name, agent_instance) tuples.
        case_summary: Clinical case summary string.
        guidelines: Full guidelines dict keyed by specialty.
        case_id: Optional case identifier for publishing agent messages.

    Returns:
        Tuple of (findings dict, failed_agents list).
    """
    findings: Dict[str, SpecialtyFindings] = {}
    failed_agents: List[str] = []

    def _call_agent(specialty: str, agent: SpecialtyAgentBase) -> Tuple[str, Optional[SpecialtyFindings]]:
        """Invoke a single specialty agent; return (specialty, findings_or_None)."""
        specialty_guidelines = guidelines.get(specialty, [])
        _emit_agent_message(case_id, specialty.capitalize(), f"Starting {specialty} analysis…")
        try:
            result = agent.analyze(case_summary, specialty_guidelines)
            logger.info("Agent '%s' completed successfully.", specialty)
            _emit_agent_message(
                case_id,
                specialty.capitalize(),
                f"Analysis complete. Summary: {result.summary[:200]}{'…' if len(result.summary) > 200 else ''}",
            )
            return specialty, result
        except SpecialtyAgentError as exc:
            logger.warning("Agent '%s' failed: %s", specialty, exc)
            _emit_agent_message(case_id, specialty.capitalize(), f"Agent failed: {exc}")
            return specialty, None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Agent '%s' raised unexpected error: %s", specialty, exc)
            _emit_agent_message(case_id, specialty.capitalize(), f"Unexpected error: {exc}")
            return specialty, None

    max_workers = min(len(specialty_agent_pairs), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_specialty = {
            executor.submit(_call_agent, specialty, agent): specialty
            for specialty, agent in specialty_agent_pairs
        }

        for future in as_completed(future_to_specialty):
            specialty, result = future.result()
            if result is not None:
                findings[specialty] = result
            else:
                failed_agents.append(specialty)

    return findings, failed_agents
