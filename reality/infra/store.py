"""Persistence for spatial worlds: JSON files on disk."""

from __future__ import annotations

import json
import os

from reality.core.models import SpatialWorld
from reality.core.pipeline import load_world
from reality.core.world import RealityWorld, WorldValidationError
from reality.infra.adapters import WorldStateStore


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


class JsonFileWorldStore(WorldStateStore):
    """WorldStateStore backed by a single JSON file (v0: no database)."""

    def save(self, world: RealityWorld, path: str) -> None:
        save_world(world, path)  # type: ignore[arg-type]

    def load(self, path: str) -> RealityWorld:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        world = RealityWorld.from_dict(data)
        problems = world.validate()
        if problems:
            raise WorldValidationError("; ".join(problems))
        return world


def load_reality_world(path: str) -> RealityWorld:
    """Load a reality/v0 world file (also accepts legacy spatial files)."""
    return JsonFileWorldStore().load(path)
