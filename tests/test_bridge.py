"""Tests for the WORLD -> REALITY bridge."""

import pytest

from reality.core.bridge import Bridge
from reality.core.fleet import TASK_ASSIGNED, TASK_QUEUED, FleetManager
from reality.core.models import Point, Zone
from reality.core.world import RealityWorld


def _fleet() -> FleetManager:
    world = RealityWorld()
    world.spatial.zones["depot"] = Zone(
        id="depot",
        name="Depot",
        polygon=[Point(0, 0), Point(20, 0), Point(20, 15), Point(0, 15)],
    )
    world.spatial.zones["field-north"] = Zone(
        id="field-north",
        name="Field North",
        polygon=[Point(0, 20), Point(20, 20), Point(20, 40), Point(0, 40)],
    )
    fleet = FleetManager(world)
    fleet.register_robot(
        "r-hauler-1",
        "Hauler-1",
        Point(10, 7),
        "depot",
        {"navigate", "lift_heavy", "tow"},
    )
    fleet.register_robot(
        "r-scout-1",
        "Scout-1",
        Point(10, 30),
        "field-north",
        {"navigate", "survey"},
    )
    return fleet


def _mission(**overrides):
    state = {
        "objective": "Survey and tow",
        "status": "planned",
        "steps": [
            {
                "name": "Survey field-north",
                "capabilities": ["survey"],
                "zone": "field-north",
                "priority": 5,
            },
            {
                "name": "Tow trailer",
                "capabilities": ["tow"],
                "zone": "depot",
                "priority": 10,
            },
        ],
    }
    state.update(overrides)
    return state


def test_materialize_creates_tasks():
    fleet = _fleet()
    tasks = Bridge(_mission(), fleet).materialize()
    assert len(tasks) == 2
    assert tasks[0].name == "Survey field-north"
    assert tasks[0].required_capabilities == {"survey"}
    assert tasks[0].target_zone == "field-north"
    assert tasks[0].priority == 5
    assert tasks[0].status == TASK_QUEUED


def test_materialize_is_idempotent():
    fleet = _fleet()
    bridge = Bridge(_mission(), fleet)
    first = bridge.materialize()
    second = bridge.materialize()
    assert len(first) == 2
    assert len(second) == 0  # already materialized, no duplicates


def test_materialize_skips_non_materializable():
    fleet = _fleet()
    assert Bridge(_mission(status="complete"), fleet).materialize() == []
    assert Bridge(_mission(status="cancelled"), fleet).materialize() == []


def test_materialize_empty_steps():
    fleet = _fleet()
    assert Bridge(_mission(steps=[]), fleet).materialize() == []


def test_tasks_assignable_after_materialize():
    fleet = _fleet()
    Bridge(_mission(), fleet).materialize()
    assigned = fleet.assign_all()
    assert len(assigned) == 2
    by_name = {t.name: t for t in assigned}
    # Survey needs "survey" -> only r-scout-1.
    assert by_name["Survey field-north"].assigned_robot == "r-scout-1"
    # Tow needs "tow" -> only r-hauler-1.
    assert by_name["Tow trailer"].assigned_robot == "r-hauler-1"


def test_sync_status():
    fleet = _fleet()
    bridge = Bridge(_mission(), fleet)
    bridge.materialize()
    fleet.assign_all()
    counts = bridge.sync_status()
    assert counts[TASK_ASSIGNED] == 2
    # Non-mission tasks are excluded.
    fleet.submit_task("other", "Unrelated", set())
    counts = bridge.sync_status()
    assert counts[TASK_ASSIGNED] == 2
    assert TASK_QUEUED not in counts


def test_legacy_step_shape_rejected():
    fleet = _fleet()
    with pytest.raises(TypeError, match="list of step objects"):
        Bridge(_mission(steps={"a": 1}), fleet).materialize()


def test_step_defaults():
    fleet = _fleet()
    tasks = Bridge(_mission(steps=[{"name": "Simple"}]), fleet).materialize()
    assert len(tasks) == 1
    assert tasks[0].required_capabilities == set()
    assert tasks[0].target_zone is None
    assert tasks[0].priority == 0
