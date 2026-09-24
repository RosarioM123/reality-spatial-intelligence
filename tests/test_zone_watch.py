"""Tests for zone watch."""

from reality.core.fleet import FleetManager
from reality.core.models import Point, Zone
from reality.core.world import RealityWorld
from reality.core.zone_watch import ZoneWatch


def _fleet() -> FleetManager:
    world = RealityWorld()
    world.spatial.zones["depot"] = Zone(
        id="depot",
        name="Depot",
        polygon=[Point(0, 0), Point(20, 0), Point(20, 15), Point(0, 15)],
    )
    world.spatial.zones["field"] = Zone(
        id="field",
        name="Field",
        polygon=[Point(0, 20), Point(20, 20), Point(20, 40), Point(0, 40)],
    )
    fleet = FleetManager(world)
    fleet.register_robot("r1", "R1", Point(10, 7), "depot", {"tow"})
    return fleet


def test_no_violation_when_in_zone():
    fleet = _fleet()
    fleet.submit_task("t1", "Tow", {"tow"}, target_zone="depot")
    fleet.assign_next()
    assert ZoneWatch(fleet).check() == []


def test_violation_when_wrong_zone():
    fleet = _fleet()
    fleet.submit_task("t1", "Tow", {"tow"}, target_zone="field")
    fleet.assign_next()
    # r1 is in depot, task wants field.
    violations = ZoneWatch(fleet).check()
    assert len(violations) == 1
    v = violations[0]
    assert v.robot_id == "r1"
    assert v.expected_zone == "field"
    assert v.actual_zone == "depot"


def test_violation_when_outside_all_zones():
    fleet = _fleet()
    entity = fleet.world.spatial.entities["r1"]
    entity.position = Point(999, 999)
    fleet.submit_task("t1", "Tow", {"tow"}, target_zone="depot")
    fleet.assign_next()
    violations = ZoneWatch(fleet).check()
    assert len(violations) == 1
    assert violations[0].actual_zone is None


def test_no_check_without_target_zone():
    fleet = _fleet()
    fleet.submit_task("t1", "Tow", {"tow"})  # no target zone
    fleet.assign_next()
    assert ZoneWatch(fleet).check() == []


def test_no_check_without_assignment():
    fleet = _fleet()
    fleet.submit_task("t1", "Tow", {"tow"}, target_zone="field")
    # Not assigned yet.
    assert ZoneWatch(fleet).check() == []


def test_track_boundary_events():
    fleet = _fleet()
    watch = ZoneWatch(fleet)
    events = watch.track("r1", Point(10, 7), 1000.0)
    assert events == []  # first sighting, no event
    events = watch.track("r1", Point(10, 30), 1001.0)
    kinds = [e.kind for e in events]
    assert "exit" in kinds
    assert "enter" in kinds
