"""Geofence monitor tests."""

import pytest

from reality.core.geofence import ENTER, EXIT, GeofenceMonitor
from reality.core.models import Point, Zone

ROOM_A = Zone(
    id="a",
    name="Room A",
    polygon=[Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)],
)
ROOM_B = Zone(
    id="b",
    name="Room B",
    polygon=[Point(20, 0), Point(30, 0), Point(30, 10), Point(20, 10)],
)


@pytest.fixture
def monitor():
    return GeofenceMonitor({"a": ROOM_A, "b": ROOM_B})


def test_first_sighting_is_silent_baseline(monitor):
    assert monitor.update("e1", Point(5, 5), ts=1.0) == []
    assert monitor.current_zone("e1") == "a"


def test_enter_and_exit(monitor):
    monitor.update("e1", Point(5, 5), ts=1.0)
    events = monitor.update("e1", Point(50, 50), ts=2.0)
    assert [(e.kind, e.zone_id) for e in events] == [(EXIT, "a")]
    assert monitor.current_zone("e1") is None
    events = monitor.update("e1", Point(25, 5), ts=3.0)
    assert [(e.kind, e.zone_id) for e in events] == [(ENTER, "b")]


def test_direct_zone_to_zone_emits_exit_then_enter(monitor):
    monitor.update("e1", Point(5, 5), ts=1.0)
    events = monitor.update("e1", Point(25, 5), ts=2.0)
    assert [(e.kind, e.zone_id) for e in events] == [(EXIT, "a"), (ENTER, "b")]
    assert all(e.entity_id == "e1" and e.ts == 2.0 for e in events)


def test_no_event_when_zone_unchanged(monitor):
    monitor.update("e1", Point(5, 5), ts=1.0)
    assert monitor.update("e1", Point(6, 6), ts=2.0) == []
    assert monitor.update("e1", Point(50, 50), ts=3.0) != []
    assert monitor.update("e1", Point(60, 60), ts=4.0) == []


def test_boundary_counts_as_inside(monitor):
    monitor.update("e1", Point(50, 50), ts=1.0)
    events = monitor.update("e1", Point(0, 5), ts=2.0)  # on Room A's edge
    assert [(e.kind, e.zone_id) for e in events] == [(ENTER, "a")]


def test_emit_initial_opt_in():
    monitor = GeofenceMonitor({"a": ROOM_A}, emit_initial=True)
    events = monitor.update("e1", Point(5, 5), ts=1.0)
    assert [(e.kind, e.zone_id) for e in events] == [(ENTER, "a")]
    # ...but not for an entity starting in open space.
    assert monitor.update("e2", Point(50, 50), ts=1.0) == []


def test_multiple_entities_tracked_independently(monitor):
    monitor.update("e1", Point(5, 5), ts=1.0)
    monitor.update("e2", Point(25, 5), ts=1.0)
    events = monitor.update("e1", Point(25, 5), ts=2.0)
    assert [(e.kind, e.zone_id) for e in events] == [(EXIT, "a"), (ENTER, "b")]
    assert monitor.current_zone("e2") == "b"
    assert monitor.update("e2", Point(26, 6), ts=3.0) == []


def test_reset(monitor):
    monitor.update("e1", Point(5, 5), ts=1.0)
    monitor.reset("e1")
    assert monitor.current_zone("e1") is None
    # After reset the next sighting is a fresh baseline again.
    assert monitor.update("e1", Point(25, 5), ts=2.0) == []
    assert monitor.current_zone("e1") == "b"
    monitor.reset()
    assert monitor.current_zone("e1") is None


def test_event_serializes():
    monitor = GeofenceMonitor({"a": ROOM_A})
    monitor.update("e1", Point(5, 5), ts=1.0)
    (event,) = monitor.update("e1", Point(50, 50), ts=2.0)
    d = event.to_dict()
    assert d == {"entity_id": "e1", "zone_id": "a", "kind": "exit", "ts": 2.0}


def test_accepts_spatial_world(office_data):
    from reality.core.models import SpatialWorld

    world = SpatialWorld.from_dict(
        {
            "zones": office_data["zones"],
            "entities": office_data["entities"],
            "adjacency": office_data.get("adjacency", {}),
        }
    )
    monitor = GeofenceMonitor(world)
    first = next(iter(world.zones.values()))
    # A vertex is on the boundary, which counts as inside.
    assert monitor.locate(first.polygon[0]) is not None
