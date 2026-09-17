"""Configuration for the reality pipeline.

Settings are plain dataclasses; environment variables override defaults.
Prefix: REALITY_
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the spatial pipeline."""

    data_dir: str = "data"
    default_radius: float = 5.0
    default_floor: int = 0
    # Maximum entities returned by a single proximity query (safety cap).
    max_results: int = 50


def get_settings() -> Settings:
    """Build settings, applying REALITY_* environment overrides."""
    data_dir = os.environ.get("REALITY_DATA_DIR", "data")
    try:
        default_radius = float(os.environ.get("REALITY_DEFAULT_RADIUS", "5.0"))
    except ValueError:
        default_radius = 5.0
    try:
        max_results = int(os.environ.get("REALITY_MAX_RESULTS", "50"))
    except ValueError:
        max_results = 50
    return Settings(
        data_dir=data_dir,
        default_radius=default_radius,
        max_results=max_results,
    )
