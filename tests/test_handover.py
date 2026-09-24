"""Tests for shift handover reports."""

import time

from reality.core.fleet import FleetManager
from reality.core.handover import generate_handover
from reality.core.incidents import IncidentManager
from reality.core.models import Point, Zone
from reality.core.telemetry import Heartbeat, TelemetryMonitor
from reality.core.world import RealityWorld


def _setup():
    world = RealityWorld()
    world.spatial.zones["depot"] = Zone(
        id="depot",
        name="Depot",
        polygon=[Point(0, 0), Point(20, 0), Point(20, 15), Point(0, 15)],
    )
    fleet = FleetManager(world)
    fleet.register_robot("r1", "R1", Point(10, 7), "depot", {"tow"}, battery=90.0)
    fleet.register_robot("r2", "R2", Point(10, 7), "depot", {"tow"}, battery=10.0)
    incidents = IncidentManager()
    monitor = TelemetryMonitor(stale_after=30.0)
    return fleet, incidents, monitor


def test_handover_clean_shift():
    fleet, incidents, monitor = _setup()
    now = 1_700_000_000.0
    monitor.ingest(Heartbeat("r1", now - 5, battery=90.0))
    monitor.ingest(Heartbeat("r2", now - 5, battery=10.0))
    report = generate_handover(fleet, incidents, monitor, shift_name="night", now=now)
    assert "SHIFT HANDOVER: night" in report
    assert "clean shift" in report
    assert "LOW BATTERY: r2" in report
    assert "robots: 2" in report


def test_handover_with_incidents():
    fleet, incidents, monitor = _setup()
    now = 1_700_000_000.0
    inc = incidents.raise_incident("Robot dark", robot_id="r1", severity="critical")
    # Backdate for a deterministic age.
    inc.created_at = now - 3600
    report = generate_handover(fleet, incidents, monitor, now=now)
    assert "OPEN INCIDENTS (1)" in report
    assert "[critical]" in report
    assert "60m old" in report


def test_handover_flags_uncovered_telemetry():
    fleet, incidents, monitor = _setup()
    now = 1_700_000_000.0
    monitor.ingest(Heartbeat("r1", now - 100))  # stale, no incident
    monitor.ingest(Heartbeat("r2", now - 5))
    report = generate_handover(fleet, incidents, monitor, now=now)
    assert "TELEMETRY FLAGS" in report
    assert "r1: degraded" in report


def test_handover_excludes_covered_robots():
    fleet, incidents, monitor = _setup()
    now = 1_700_000_000.0
    monitor.ingest(Heartbeat("r1", now - 1000))
    incidents.raise_incident("Robot dark", robot_id="r1")
    report = generate_handover(fleet, incidents, monitor, now=now)
    # r1 has an incident, so it shouldn't appear as an uncovered flag.
    telemetry_section = report.split("TELEMETRY FLAGS")[1]
    assert "r1" not in telemetry_section
