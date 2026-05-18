"""
Data loader service for guidelines and sample cases.

Reads JSON data files relative to the backend package root.
"""

import json
import os
from pathlib import Path

# Resolve the backend package root (parent of this file's directory)
_PACKAGE_ROOT = Path(__file__).parent.parent
_DATA_DIR = _PACKAGE_ROOT / "data"


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
