"""Zone watch: are robots where they're supposed to be?

A robot with an assigned task has an expected zone (the task's target).
If telemetry places it somewhere else — wrong zone, or no zone at all —
that's a zone violation. This module checks fleet positions against
expectations and reports violations for the incident pipeline.

It sits on top of the existing GeofenceMonitor (boundary-crossing
detection) and adds the ops question: "should this robot be here?"
"""

from __future__ import annotations

from dataclasses import dataclass

from reality.core.fleet import FleetManager
from reality.core.geofence import GeofenceMonitor
from reality.core.models import Point


@dataclass
class ZoneViolation:
    """A robot outside its expected zone."""

    robot_id: str
    expected_zone: str | None
    actual_zone: str | None
    detail: str

    def to_dict(self) -> dict:
        return {
            "robot_id": self.robot_id,
            "expected_zone": self.expected_zone,
            "actual_zone": self.actual_zone,
            "detail": self.detail,
        }


class ZoneWatch:
    """Checks fleet positions against task-assigned zones."""

    def __init__(self, fleet: FleetManager):
        self.fleet = fleet
        self.monitor = GeofenceMonitor(fleet.world.spatial)

    def check(self) -> list[ZoneViolation]:
        """One sweep: every robot with an assigned task is checked
        against that task's target zone."""
        violations = []
        for task in self.fleet.tasks.values():
            if not task.assigned_robot or not task.target_zone:
                continue
            robot_id = task.assigned_robot
            entity = self.fleet.world.spatial.entities.get(robot_id)
            if entity is None:
                continue
            actual = self.monitor.locate(entity.position)
            actual_zone = actual.id if actual else None
            if actual_zone != task.target_zone:
                violations.append(
                    ZoneViolation(
                        robot_id=robot_id,
                        expected_zone=task.target_zone,
                        actual_zone=actual_zone,
                        detail=(
                            f"{robot_id} assigned to {task.target_zone!r} "
                            f"for {task.name!r}, actually in "
                            f"{actual_zone!r}"
                        ),
                    )
                )
        return violations

    def track(self, robot_id: str, position: Point, ts: float) -> list:
        """Feed a position fix through the boundary-crossing monitor.
        Returns GeofenceEvents (enter/exit) for incident enrichment."""
        return self.monitor.update(robot_id, position, ts)
