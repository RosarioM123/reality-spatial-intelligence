"""Persistence for spatial worlds: JSON files on disk."""

from __future__ import annotations

import json
import os

from reality.core.models import SpatialWorld
from reality.core.pipeline import load_world


def save_world(world: SpatialWorld, path: str) -> str:
    """Write a world to a JSON file. Returns the path written."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(world.to_dict(), f, indent=2)
    return path


def load_world_path(path: str) -> SpatialWorld:
    """Load and validate a world from a JSON file."""
    with open(path, encoding="utf-8") as f:
        return load_world(json.load(f))
