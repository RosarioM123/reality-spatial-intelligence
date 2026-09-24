"""Field operations demo: the full operating-layer loop.

    python examples/field_ops_demo.py

1. A mission arrives from WORLD -> bridge materializes fleet tasks.
2. Fleet manager assigns tasks by capability + proximity.
3. Robots report heartbeats; telemetry detects the dark ones.
4. Detections become tracked incidents (deduped, escalated, resolved).
5. Mission rollup goes back to WORLD.

This is the "operating layer for machines in the field" in miniature:
monitor -> detect -> track -> resolve, with the mission as source of truth.
"""

import json
import time

from reality.core.bridge import Bridge
from reality.core.fleet import FleetManager
from reality.core.handover import generate_handover
from reality.core.incidents import (
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    SOURCE_GEOFENCE,
    SOURCE_TELEMETRY,
    IncidentManager,
)
from reality.core.telemetry import (
    ALERT_CRITICAL,
    ALERT_LOST,
    Heartbeat,
    TelemetryMonitor,
)
from reality.core.world import RealityWorld
from reality.core.zone_watch import ZoneWatch

_ALERT_SEVERITY = {ALERT_CRITICAL: SEVERITY_CRITICAL, ALERT_LOST: SEVERITY_CRITICAL}


def main() -> None:
    with open("examples/fleet.json", encoding="utf-8") as f:
        world = RealityWorld.from_dict(json.load(f))
    fleet = FleetManager(world)
    monitor = TelemetryMonitor(stale_after=30.0)
    incidents = IncidentManager()
    print(f"fleet loaded: {len(fleet.robots())} robots")

    # 1-2. Mission -> tasks -> assignment.
    mission_state = {
        "objective": "Survey field-south, tow trailer to depot",
        "status": "planned",
        "steps": [
            {
                "name": "Survey field-south",
                "capabilities": ["survey", "camera"],
                "zone": "field-south",
                "priority": 5,
            },
            {
                "name": "Tow trailer to depot",
                "capabilities": ["tow"],
                "zone": "depot",
                "priority": 10,
            },
        ],
    }
    bridge = Bridge(mission_state, fleet)
    print(f"bridge: {len(bridge.materialize())} mission steps -> fleet tasks")
    for task in fleet.assign_all():
        print(f"  assigned {task.name!r} -> {task.assigned_robot}")

    # 3. Heartbeats in. Two robots go dark.
    now = time.time()
    monitor.ingest_many(
        [
            Heartbeat(
                "r-hauler-1",
                now - 5,
                battery=88.0,
                zone_id="depot",
                status="executing",
            ),
            Heartbeat(
                "r-hauler-2",
                now - 12,
                battery=76.0,
                zone_id="field-north",
                status="idle",
            ),
            Heartbeat(
                "r-scout-1",
                now - 300,
                battery=18.0,
                zone_id="field-south",
                status="idle",
            ),
            # r-scout-2 never checks in.
        ]
    )

    # 4. Detections -> incidents (deduped by robot).
    robot_ids = [r.id for r in fleet.robots()]
    health = monitor.fleet_health(robot_ids, now=now)
    print("\ntelemetry:")
    for robot in health["robots"]:
        h = monitor.health(robot["robot_id"], now=now)
        age = h.seconds_since_heartbeat
        age_s = f"{age:.0f}s ago" if age is not None else "never"
        print(f"  {h.robot_id}: {h.alert} (last seen {age_s})")
        if h.alert in _ALERT_SEVERITY:
            incidents.raise_incident(
                title=f"Robot {h.robot_id} {h.alert} (last seen {age_s})",
                robot_id=h.robot_id,
                source=SOURCE_TELEMETRY,
                severity=_ALERT_SEVERITY[h.alert],
                dedup_key=f"{h.robot_id}-dark",
            )

    # 4b. Zone watch: is anyone where they shouldn't be?
    # Move r-hauler-2 to field-south (wrong zone for its idle state is
    # fine, but let's simulate a stray by assigning it a depot task).
    fleet.submit_task(
        "stray-check",
        "Return to depot",
        {"navigate"},
        target_zone="depot",
        priority=1,
    )
    stray_task = fleet.assign_next()
    if stray_task:
        # r-hauler-2 gets it, but it's in field-north — violation.
        watch = ZoneWatch(fleet)
        for v in watch.check():
            incidents.raise_incident(
                title=f"Zone violation: {v.detail}",
                robot_id=v.robot_id,
                source=SOURCE_GEOFENCE,
                severity=SEVERITY_WARNING,
                dedup_key=f"{v.robot_id}-zone",
            )
            print(
                f"  zone violation: {v.robot_id} in {v.actual_zone!r}, "
                f"expected {v.expected_zone!r}"
            )

    # Ops works the incident queue.
    open_incs = incidents.open_incidents()
    print(f"\nincidents: {len(open_incs)} open")
    for inc in open_incs:
        print(f"  [{inc.severity}] {inc.title}")
    if open_incs:
        first = open_incs[0]
        incidents.acknowledge(first.id, actor="ops-lead", note="Dispatching recovery")
        print(f"  acknowledged {first.id}")

    # 5. Rollup for WORLD.
    print(f"\nmission rollup: {bridge.sync_status()}")
    print(f"incident summary: {incidents.summary()}")

    # 6. Shift handover for the incoming team.
    print()
    print(generate_handover(fleet, incidents, monitor, shift_name="day-shift"))


if __name__ == "__main__":
    main()
