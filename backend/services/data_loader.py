"""
Data loader service for guidelines and sample cases.

Reads JSON data files relative to the backend package root.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Try multiple possible locations for the data directory
# to handle different deployment environments (local, Docker, Render)
def _find_data_dir() -> Path:
    candidates = [
        # Standard: running from repo root as `python -m backend.main`
        Path(__file__).parent.parent / "data",
        # Docker: COPY . ./backend → /app/backend/data
        Path("/app/backend/data"),
        # Render: rootDir=backend, files at /opt/render/project/src/data
        Path("/opt/render/project/src/data"),
        # Running directly from backend/ directory
        Path(__file__).parent / "data",
        # CWD-relative fallback
        Path(os.getcwd()) / "data",
        Path(os.getcwd()) / "backend" / "data",
    ]
    for candidate in candidates:
        if candidate.exists():
            logger.info("Data directory found at: %s", candidate)
            return candidate
    # Return the most likely path even if it doesn't exist yet
    fallback = Path(__file__).parent.parent / "data"
    logger.warning("Data directory not found in any candidate path, using: %s", fallback)
    return fallback

_DATA_DIR = _find_data_dir()


def load_guidelines() -> dict:
    """
    Load clinical guidelines from data/guidelines.json.

    Returns a dict keyed by specialty name, where each value is a list
    of guideline strings.

    Example:
        {
            "radiology": ["Guideline 1: ...", ...],
            "oncology": [...],
            ...
        }
    """
    guidelines_path = _DATA_DIR / "guidelines.json"
    with open(guidelines_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sample_cases() -> list:
    """
    Load sample clinical cases from data/sample_cases.json.

    Returns a list of sample case dicts, each containing:
        - id: str
        - title: str
        - specialties: List[str]
        - text: str

    Example:
        [
            {
                "id": "sample-1",
                "title": "Chest Pain with Imaging",
                "specialties": ["cardiology", "radiology"],
                "text": "..."
            },
            ...
        ]
    """
    cases_path = _DATA_DIR / "sample_cases.json"
    with open(cases_path, "r", encoding="utf-8") as f:
        return json.load(f)
