"""End-to-end: WORLD mission -> REALITY fleet -> telemetry.

This demo runs the full operating-layer story without the WORLD package
installed — it uses a mission state dict in the shape WORLD produces
(see world/examples/fleet_mission/ for the WORLD half).

    python examples/field_ops_demo.py

What it shows:
1. A mission (WORLD's output) materializes into fleet tasks via the bridge.
2. The fleet manager assigns tasks to robots by capability + proximity.
3. Robots report heartbeats; telemetry flags the one that goes dark.
"""

import json
import time

from reality.core.bridge import Bridge
from reality.core.fleet import FleetManager
from reality.core.telemetry import Heartbeat, TelemetryMonitor
from reality.core.world import RealityWorld


def main() -> None:
    # 1. Load the field. Robots are already registered in fleet.json.
    with open("examples/fleet.json", encoding="utf-8") as f:
        world = RealityWorld.from_dict(json.load(f))
    fleet = FleetManager(world)
    print(f"fleet loaded: {len(fleet.robots())} robots")

    # 2. A mission arrives from WORLD (mission planner's output).
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
    tasks = Bridge(mission_state, fleet).materialize()
    print(f"bridge: {len(tasks)} mission steps -> fleet tasks")

    # 3. Assign. Capability + proximity decide.
    for task in fleet.assign_all():
        print(f"  assigned {task.name!r} -> {task.assigned_robot}")

    # 4. Robots report in. One goes dark.
    now = time.time()
    monitor = TelemetryMonitor(stale_after=30.0)
    monitor.ingest_many(
        [
            Heartbeat("r-hauler-1", now - 5, battery=88.0, zone_id="depot",
                      status="executing"),
            Heartbeat("r-hauler-2", now - 12, battery=76.0,
                      zone_id="field-north", status="idle"),
            Heartbeat("r-scout-1", now - 300, battery=18.0,
                      zone_id="field-south", status="idle"),
            # r-scout-2 never checks in.
        ]
    )
    health = monitor.fleet_health(
        [r.id for r in fleet.robots()], now=now
    )
    print("\ntelemetry:")
    for robot in health["robots"]:
        age = robot["seconds_since_heartbeat"]
        age_s = f"{age:.0f}s ago" if age is not None else "never"
        print(f"  {robot['robot_id']}: {robot['alert']} (last seen {age_s})")
    if health["needs_attention"]:
        print(f"needs attention: {', '.join(health['needs_attention'])}")

    # 5. Mission-level rollup for WORLD to persist.
    print(f"\nmission rollup: {Bridge(mission_state, fleet).sync_status()}")


if __name__ == "__main__":
    main()
