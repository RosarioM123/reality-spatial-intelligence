"""WORLD -> REALITY bridge: missions become fleet tasks.

This is the integration point between the two layers:

- WORLD persists the mission: what must be done, its steps, its
  constraints. Versioned, invariant-checked, hash-chained. It survives
  process death, network partitions, and shift changes.
- REALITY executes the mission: the fleet manager turns mission steps
  into tasks, assigns them to robots by capability and proximity, and
  verifies outcomes against independent observations.

The bridge reads a mission from a WORLD handle and materializes it as
fleet tasks. It never mutates the mission — the mission is the source
of truth; the fleet is the execution.

Mission schema (WORLD state):
    {
        "objective": str,
        "steps": [
            {"name": str, "capabilities": [str], "zone": str | None,
             "priority": int},
            ...
        ],
        "assigned_robot": str | None,   # optional: pin a step to a robot
        "status": "planned" | "in_progress" | "complete",
    }

Usage:
    from world import World
    from reality.core.bridge import Bridge

    mission = World("mission-alpha")            # WORLD handle
    bridge = Bridge(mission.state(), fleet)     # state dict, no dependency
    tasks = bridge.materialize()                # steps -> FleetTasks
"""

from __future__ import annotations

from typing import Any

from reality.core.fleet import FleetManager, FleetTask

# Mission states the bridge will materialize. Anything else (e.g.
# "complete", "cancelled") is left alone.
MATERIALIZABLE_STATES = {"planned", "in_progress"}


class Bridge:
    """Turns a WORLD mission into REALITY fleet tasks."""

    def __init__(self, mission_state: dict[str, Any], fleet: FleetManager):
        self.mission_state = mission_state
        self.fleet = fleet

    def materialize(self) -> list[FleetTask]:
        """Create fleet tasks from mission steps.

        Idempotent per step name: steps already materialized (a task
        with the same id exists) are skipped, so re-running the bridge
        after a restart doesn't duplicate work.
        """
        status = self.mission_state.get("status")
        if status not in MATERIALIZABLE_STATES:
            return []

        steps = self.mission_state.get("steps", [])
        if isinstance(steps, dict):
            # Legacy shape: {"steps": [...], "steps_remaining": n} —
            # not supported by the bridge; use the step-object shape.
            raise TypeError(
                "bridge expects steps as a list of step objects, "
                f"got {type(steps).__name__}"
            )

        tasks = []
        for i, step in enumerate(steps):
            task_id = f"mission-{i}-{_slug(step.get('name', f'step-{i}'))}"
            if task_id in self.fleet.tasks:
                continue
            task = self.fleet.submit_task(
                task_id=task_id,
                name=str(step.get("name", f"step-{i}")),
                required_capabilities=set(step.get("capabilities", [])),
                target_zone=step.get("zone"),
                priority=int(step.get("priority", 0)),
                parameters={"mission_step": i},
            )
            tasks.append(task)
        return tasks

    def sync_status(self) -> dict[str, int]:
        """Roll up fleet task outcomes into a mission-level summary.

        Returns counts by task status. The caller writes these back to
        the WORLD mission (the bridge never writes to WORLD itself —
        that's the mission owner's job, keeping the authority boundary
        clean).
        """
        counts: dict[str, int] = {}
        for task in self.fleet.tasks.values():
            if task.parameters.get("mission_step") is None:
                continue
            counts[task.status] = counts.get(task.status, 0) + 1
        return counts


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
