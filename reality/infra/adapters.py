"""Adapter interfaces: the seams where the simulator can one day be
replaced by real-world inputs.

The v0 thesis is simulation-first, but nothing in core depends on the
simulator: core talks only to these three interfaces.

  ObservationSource  -- where evidence comes from
      today: SimObservationSource (reads simulated ground truth)
      later: camera pipelines, GPS feeds, IoT hubs, enterprise APIs,
             human reports, robot telemetry

  ActionExecutor     -- what carries actions out in the world
      today: SimActionExecutor (mutates simulated ground truth)
      later: robot controllers, smart-building APIs, notification
             services, warehouse management systems

  WorldStateStore    -- where the world persists
      today: JsonFileWorldStore (a JSON file)
      later: any durable store; the interface is deliberately tiny
"""

from __future__ import annotations

import abc
from typing import Any

from reality.core.models import Action, Observation
from reality.core.world import RealityWorld


class ObservationSource(abc.ABC):
    """Produces observations about the world."""

    @abc.abstractmethod
    def poll(self, world: RealityWorld) -> list[Observation]:
        """Return new observations since the last poll (may be empty)."""


class ActionExecutor(abc.ABC):
    """Carries an authorized action out in the (real or simulated) world.

    Returns a report dict: {"success": bool, "message": str}. The report is
    the executor's CLAIM about what happened -- it is not trusted as ground
    truth. Verification compares the action's expected effect against later
    observations.
    """

    @abc.abstractmethod
    def execute(self, action: Action) -> dict[str, Any]:
        ...


class WorldStateStore(abc.ABC):
    """Persistence for whole world snapshots."""

    @abc.abstractmethod
    def save(self, world: RealityWorld, path: str) -> None:
        ...

    @abc.abstractmethod
    def load(self, path: str) -> RealityWorld:
        ...
