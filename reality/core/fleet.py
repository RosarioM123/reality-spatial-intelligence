"""Fleet operations: the operating layer for robots in the field.

A FleetManager coordinates a fleet of robots working in a shared physical
space. It handles robot registration (capabilities, battery, status), task
submission with capability requirements, and assignment that matches tasks
to the best robot by capability fit and spatial proximity.

Tasks flow through the existing action lifecycle (propose -> authorize ->
execute -> observe -> verify), so every assignment is constraint-checked
and every outcome is independently verified — the fleet layer adds
coordination on top of the trusted primitives, it doesn't bypass them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from reality.core import geometry as _geometry
from reality.core.models import Entity, Observation, Point
from reality.core.world import RealityWorld

# Observation source for fleet-manager state changes. Assignments and
# releases go through the observation channel like everything else, so
# they carry provenance and confidence instead of bypassing them.
SOURCE_FLEET_MANAGER = "fleet-manager"

# Robot operational states. A robot is assignable only when idle.
ROBOT_IDLE = "idle"
ROBOT_ASSIGNED = "assigned"
ROBOT_EXECUTING = "executing"
ROBOT_CHARGING = "charging"
ROBOT_FAULT = "fault"
ROBOT_OFFLINE = "offline"

ASSIGNABLE_STATES = {ROBOT_IDLE}

# Task lifecycle states.
TASK_QUEUED = "queued"
TASK_ASSIGNED = "assigned"
TASK_IN_PROGRESS = "in_progress"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"
TASK_CANCELLED = "cancelled"


@dataclass
class FleetTask:
    """A unit of work for the fleet.

    required_capabilities: e.g. {"lift_heavy", "navigate"}. A robot must
        have ALL of them to be eligible.
    target_zone: where the work happens (used for proximity scoring).
    priority: higher runs first when multiple tasks are queued.
    """

    id: str
    name: str
    required_capabilities: set[str] = field(default_factory=set)
    target_zone: str | None = None
    priority: int = 0
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = TASK_QUEUED
    assigned_robot: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "required_capabilities": sorted(self.required_capabilities),
            "target_zone": self.target_zone,
            "priority": self.priority,
            "parameters": self.parameters,
            "status": self.status,
            "assigned_robot": self.assigned_robot,
        }


class FleetManager:
    """Coordinates a robot fleet inside a RealityWorld.

    Robots are Entities with kind="robot". Their fleet-relevant attributes
    live in entity.state (status, battery, capabilities) so they benefit
    from the same provenance tracking as everything else — but note the
    rule: state changes only via observations, never by direct mutation.
    The fleet manager proposes assignments; the world confirms them
    through the observation channel.
    """

    def __init__(self, world: RealityWorld):
        self.world = world
        self.tasks: dict[str, FleetTask] = {}

    # -- robot registration -------------------------------------------

    def register_robot(
        self,
        robot_id: str,
        name: str,
        position: Point,
        zone_id: str | None,
        capabilities: set[str] | list[str],
        battery: float = 100.0,
    ) -> Entity:
        """Register a robot in the fleet. Returns the backing Entity."""
        entity = Entity(
            id=robot_id,
            name=name,
            kind="robot",
            position=position,
            zone_id=zone_id,
            state={
                "status": ROBOT_IDLE,
                "battery": battery,
                "capabilities": sorted(set(capabilities)),
            },
        )
        self.world.spatial.entities[robot_id] = entity
        return entity

    def robots(self) -> list[Entity]:
        """All registered robots."""
        return [e for e in self.world.spatial.entities.values() if e.kind == "robot"]

    def robot_status(self, robot_id: str) -> dict[str, Any]:
        """Operational snapshot of one robot."""
        entity = self.world.spatial.entities.get(robot_id)
        if entity is None or entity.kind != "robot":
            raise KeyError(f"unknown robot {robot_id!r}")
        return {
            "id": entity.id,
            "name": entity.name,
            "zone_id": entity.zone_id,
            "status": entity.state.get("status", ROBOT_IDLE),
            "battery": entity.state.get("battery"),
            "capabilities": entity.state.get("capabilities", []),
            "current_task": entity.state.get("current_task"),
        }

    # -- task submission ----------------------------------------------

    def submit_task(
        self,
        task_id: str,
        name: str,
        required_capabilities: set[str] | list[str] | None = None,
        target_zone: str | None = None,
        priority: int = 0,
        parameters: dict[str, Any] | None = None,
    ) -> FleetTask:
        """Queue a task for the fleet. Returns the task."""
        if task_id in self.tasks:
            raise ValueError(f"task {task_id!r} already exists")
        task = FleetTask(
            id=task_id,
            name=name,
            required_capabilities=set(required_capabilities or ()),
            target_zone=target_zone,
            priority=priority,
            parameters=parameters or {},
        )
        self.tasks[task_id] = task
        return task

    def cancel_task(self, task_id: str) -> None:
        """Cancel a queued task. Assigned tasks must be released first."""
        task = self._get_task(task_id)
        if task.status not in (TASK_QUEUED, TASK_CANCELLED):
            raise ValueError(
                f"cannot cancel task {task_id!r} in status {task.status!r}"
            )
        task.status = TASK_CANCELLED

    # -- assignment ----------------------------------------------------

    def eligible_robots(self, task: FleetTask) -> list[Entity]:
        """Robots that have all required capabilities and are assignable."""
        eligible = []
        for robot in self.robots():
            caps = set(robot.state.get("capabilities", []))
            status = robot.state.get("status", ROBOT_IDLE)
            if task.required_capabilities <= caps and status in ASSIGNABLE_STATES:
                eligible.append(robot)
        return eligible

    def _proximity_score(self, robot: Entity, task: FleetTask) -> float:
        """Lower is better. Robots already in the target zone score 0."""
        if task.target_zone is None:
            return 0.0
        if robot.zone_id == task.target_zone:
            return 0.0
        zone = self.world.spatial.zones.get(task.target_zone)
        if zone is None or not zone.polygon:
            return float("inf")
        centroid = _geometry.centroid(zone.polygon)
        return _geometry.distance(robot.position, centroid)

    def assign_next(self) -> FleetTask | None:
        """Assign the highest-priority queued task to the best robot.

        Best = eligible, then closest to the target zone. Returns the
        assigned task, or None if nothing could be assigned.
        """
        queued = sorted(
            (t for t in self.tasks.values() if t.status == TASK_QUEUED),
            key=lambda t: (-t.priority, t.id),
        )
        for task in queued:
            candidates = self.eligible_robots(task)
            if not candidates:
                continue
            best = min(candidates, key=lambda r: self._proximity_score(r, task))
            self._assign(task, best)
            return task
        return None

    def assign_all(self) -> list[FleetTask]:
        """Keep assigning until no queued task has an eligible robot."""
        assigned = []
        while True:
            task = self.assign_next()
            if task is None:
                break
            assigned.append(task)
        return assigned

    def _assign(self, task: FleetTask, robot: Entity) -> None:
        task.status = TASK_ASSIGNED
        task.assigned_robot = robot.id
        self._observe_robot(
            robot.id,
            {"status": ROBOT_ASSIGNED, "current_task": task.id},
            context=f"assigned task {task.id} ({task.name})",
        )

    def release_robot(self, robot_id: str) -> None:
        """Mark a robot idle again (e.g. after task completion)."""
        entity = self.world.spatial.entities.get(robot_id)
        if entity is None or entity.kind != "robot":
            raise KeyError(f"unknown robot {robot_id!r}")
        self._observe_robot(
            robot_id,
            {"status": ROBOT_IDLE, "current_task": None},
            context="released from task",
        )

    def _observe_robot(
        self, robot_id: str, observed_state: dict[str, Any], context: str = ""
    ) -> None:
        """Route a fleet state change through the observation channel.

        The fleet manager never mutates entity.state directly — it reports
        what should be true, and the world applies it with provenance,
        confidence, and conflict handling like any other observation.
        """
        self.world.apply_observation(
            Observation(
                id=self.world.new_id("obs"),
                ts=time.time(),
                source=SOURCE_FLEET_MANAGER,
                entity_id=robot_id,
                observed_state=observed_state,
                confidence=1.0,
                context=context,
            )
        )

    def complete_task(self, task_id: str, success: bool = True) -> None:
        """Mark a task completed/failed and free its robot."""
        task = self._get_task(task_id)
        if task.status not in (TASK_ASSIGNED, TASK_IN_PROGRESS):
            raise ValueError(
                f"cannot complete task {task_id!r} in status {task.status!r}"
            )
        task.status = TASK_COMPLETED if success else TASK_FAILED
        if task.assigned_robot:
            self.release_robot(task.assigned_robot)

    # -- fleet health ---------------------------------------------------

    def fleet_status(self) -> dict[str, Any]:
        """Fleet-wide operational snapshot."""
        robots = [self.robot_status(r.id) for r in self.robots()]
        by_status: dict[str, int] = {}
        for r in robots:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        tasks_by_status: dict[str, int] = {}
        for t in self.tasks.values():
            tasks_by_status[t.status] = tasks_by_status.get(t.status, 0) + 1
        low_battery = [
            r["id"]
            for r in robots
            if isinstance(r["battery"], (int, float)) and r["battery"] < 20.0
        ]
        return {
            "robot_count": len(robots),
            "robots_by_status": by_status,
            "tasks_by_status": tasks_by_status,
            "low_battery": low_battery,
            "queued_tasks": tasks_by_status.get(TASK_QUEUED, 0),
        }

    # -- internals -------------------------------------------------------

    def _get_task(self, task_id: str) -> FleetTask:
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError(f"unknown task {task_id!r}")
        return task
