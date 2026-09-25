"""Tests for the fleet operations layer."""

import pytest

from reality.core.fleet import (
    ROBOT_CHARGING,
    ROBOT_FAULT,
    ROBOT_IDLE,
    SOURCE_FLEET_MANAGER,
    TASK_ASSIGNED,
    TASK_CANCELLED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_QUEUED,
    FleetManager,
)
from reality.core.models import Point, Zone
from reality.core.world import RealityWorld


def _world() -> RealityWorld:
    world = RealityWorld()
    world.spatial.zones["zone-a"] = Zone(
        id="zone-a",
        name="Zone A",
        polygon=[Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)],
    )
    world.spatial.zones["zone-b"] = Zone(
        id="zone-b",
        name="Zone B",
        polygon=[
            Point(100, 100),
            Point(110, 100),
            Point(110, 110),
            Point(100, 110),
        ],
    )
    return world


def _fleet() -> FleetManager:
    world = _world()
    fleet = FleetManager(world)
    fleet.register_robot(
        "r1",
        "Hauler-1",
        Point(5, 5),
        "zone-a",
        {"navigate", "lift_heavy"},
        battery=90.0,
    )
    fleet.register_robot(
        "r2",
        "Scout-2",
        Point(105, 105),
        "zone-b",
        {"navigate"},
        battery=15.0,
    )
    return fleet


def test_register_robot():
    fleet = _fleet()
    robots = fleet.robots()
    assert {r.id for r in robots} == {"r1", "r2"}
    status = fleet.robot_status("r1")
    assert status["status"] == ROBOT_IDLE
    assert status["battery"] == 90.0
    assert set(status["capabilities"]) == {"navigate", "lift_heavy"}


def test_robot_status_unknown():
    fleet = _fleet()
    with pytest.raises(KeyError):
        fleet.robot_status("nope")


def test_submit_and_assign_by_capability():
    fleet = _fleet()
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"}, target_zone="zone-a")
    task = fleet.assign_next()
    assert task is not None
    assert task.id == "t1"
    assert task.status == TASK_ASSIGNED
    # Only r1 can lift heavy.
    assert task.assigned_robot == "r1"


def test_capability_mismatch_leaves_task_queued():
    fleet = _fleet()
    fleet.submit_task("t1", "Weld pipe", {"weld"}, target_zone="zone-a")
    assert fleet.assign_next() is None
    assert fleet.tasks["t1"].status == TASK_QUEUED


def test_proximity_prefers_closer_robot():
    fleet = _fleet()
    # Both robots can navigate; r2 is already in zone-b.
    fleet.submit_task("t1", "Patrol", {"navigate"}, target_zone="zone-b")
    task = fleet.assign_next()
    assert task is not None
    assert task.assigned_robot == "r2"


def test_priority_ordering():
    fleet = _fleet()
    fleet.submit_task("low", "Sweep", {"navigate"}, priority=0)
    fleet.submit_task("high", "Urgent move", {"navigate"}, priority=10)
    # r1 is idle and eligible for both; high priority goes first.
    # But only one robot is eligible per task here (r2 has low battery but
    # is still idle/eligible) — just check the high-priority task assigns first.
    task = fleet.assign_next()
    assert task is not None
    assert task.id == "high"


def test_busy_robot_not_reassigned():
    fleet = _fleet()
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"})
    fleet.submit_task("t2", "Move crate", {"lift_heavy"})
    first = fleet.assign_next()
    assert first is not None and first.id == "t1"
    # r1 is now assigned; no other robot can lift heavy.
    assert fleet.assign_next() is None
    assert fleet.tasks["t2"].status == TASK_QUEUED


def test_complete_task_frees_robot():
    fleet = _fleet()
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"})
    fleet.assign_next()
    fleet.complete_task("t1", success=True)
    assert fleet.tasks["t1"].status == TASK_COMPLETED
    assert fleet.robot_status("r1")["status"] == ROBOT_IDLE
    # Robot is reusable for the next task.
    fleet.submit_task("t2", "Move crate", {"lift_heavy"})
    task = fleet.assign_next()
    assert task is not None and task.assigned_robot == "r1"


def test_complete_task_failure():
    fleet = _fleet()
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"})
    fleet.assign_next()
    fleet.complete_task("t1", success=False)
    assert fleet.tasks["t1"].status == TASK_FAILED
    assert fleet.robot_status("r1")["status"] == ROBOT_IDLE


def test_cancel_queued_task():
    fleet = _fleet()
    fleet.submit_task("t1", "Sweep", {"navigate"})
    fleet.cancel_task("t1")
    assert fleet.tasks["t1"].status == TASK_CANCELLED
    assert fleet.assign_next() is None


def test_cancel_assigned_task_rejected():
    fleet = _fleet()
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"})
    fleet.assign_next()
    with pytest.raises(ValueError):
        fleet.cancel_task("t1")


def test_duplicate_task_rejected():
    fleet = _fleet()
    fleet.submit_task("t1", "Sweep", {"navigate"})
    with pytest.raises(ValueError):
        fleet.submit_task("t1", "Sweep again", {"navigate"})


def test_fault_robot_not_eligible():
    fleet = _fleet()
    entity = fleet.world.spatial.entities["r1"]
    entity.state["status"] = ROBOT_FAULT
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"})
    assert fleet.assign_next() is None


def test_charging_robot_not_eligible():
    fleet = _fleet()
    entity = fleet.world.spatial.entities["r2"]
    entity.state["status"] = ROBOT_CHARGING
    fleet.submit_task("t1", "Patrol", {"navigate"}, target_zone="zone-b")
    task = fleet.assign_next()
    # r1 is eligible (can navigate) even though farther.
    assert task is not None
    assert task.assigned_robot == "r1"


def test_fleet_status():
    fleet = _fleet()
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"})
    fleet.submit_task("t2", "Weld pipe", {"weld"})
    fleet.assign_next()
    status = fleet.fleet_status()
    assert status["robot_count"] == 2
    assert status["robots_by_status"][ROBOT_IDLE] == 1
    assert status["tasks_by_status"][TASK_ASSIGNED] == 1
    assert status["tasks_by_status"][TASK_QUEUED] == 1
    # r2 has 15% battery.
    assert status["low_battery"] == ["r2"]


def test_assign_all():
    fleet = _fleet()
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"})
    fleet.submit_task("t2", "Patrol", {"navigate"})
    assigned = fleet.assign_all()
    assert len(assigned) == 2
    assert all(t.status == TASK_ASSIGNED for t in assigned)


def test_task_to_dict():
    fleet = _fleet()
    task = fleet.submit_task(
        "t1", "Move pallet", {"lift_heavy"}, target_zone="zone-a", priority=5
    )
    d = task.to_dict()
    assert d["id"] == "t1"
    assert d["required_capabilities"] == ["lift_heavy"]
    assert d["priority"] == 5
    assert d["status"] == TASK_QUEUED


def test_assign_goes_through_observation_channel():
    """Assignments must not mutate entity.state directly — they are
    observations, so they carry provenance."""
    fleet = _fleet()
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"})
    fleet.assign_next()

    entity = fleet.world.spatial.entities["r1"]
    assert entity.state["status"] == "assigned"
    prov = entity.state_provenance.get("status")
    assert prov is not None
    assert prov.source == SOURCE_FLEET_MANAGER
    assert prov.confidence == 1.0

    obs = fleet.world.observations[-1]
    assert obs.source == SOURCE_FLEET_MANAGER
    assert obs.entity_id == "r1"
    assert obs.observed_state["current_task"] == "t1"


def test_release_goes_through_observation_channel():
    fleet = _fleet()
    fleet.submit_task("t1", "Move pallet", {"lift_heavy"})
    fleet.assign_next()
    fleet.release_robot("r1")

    entity = fleet.world.spatial.entities["r1"]
    assert entity.state["status"] == ROBOT_IDLE
    assert entity.state.get("current_task") is None
    prov = entity.state_provenance.get("status")
    assert prov is not None
    assert prov.source == SOURCE_FLEET_MANAGER
