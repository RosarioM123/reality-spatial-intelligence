"""Closed-loop demo: WORLD -> REALITY -> WORLD.

The full story in one script:
1. WORLD persists the mission (planner defines it, checkpoints, "dies").
2. The bridge materializes mission steps into REALITY fleet tasks.
3. The fleet assigns tasks; robots execute; tasks complete.
4. Outcomes flow BACK to WORLD — the mission records what happened,
   with provenance. The loop is closed.

Run from the reality checkout with both repos present:
    python examples/closed_loop_demo.py

It finds the world package via sys.path (../world/src relative to this
file, or WORLD_SRC env var). No package dependency is created — the
bridge itself still takes only a state dict.
"""

import json
import os
import sys
import tempfile

# Locate the world package without creating a dependency.
HERE = os.path.dirname(os.path.abspath(__file__))
WORLD_SRC = os.environ.get(
    "WORLD_SRC", os.path.join(os.path.dirname(HERE), "..", "world", "src")
)
if os.path.isdir(WORLD_SRC) and WORLD_SRC not in sys.path:
    sys.path.insert(0, WORLD_SRC)

from world import World
from world.invariants import no_negative

from reality.core.bridge import Bridge
from reality.core.fleet import FleetManager
from reality.core.world import RealityWorld

MISSION = "closed-loop-demo"
INVARIANTS = [no_negative("battery_pct"), no_negative("steps_remaining")]


def main() -> None:
    os.environ.setdefault("WORLD_DIR", tempfile.mkdtemp(prefix="world-closed-loop-"))

    # 1. WORLD: the planner defines the mission.
    mission = World(MISSION, invariants=INVARIANTS)
    mission.update(
        {
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
            "outcomes": [],
        },
        actor="mission-planner",
        note="mission defined",
    )
    print("1. WORLD: mission defined and checkpointed")

    # 2. Bridge: mission -> REALITY fleet tasks.
    with open(os.path.join(HERE, "fleet.json"), encoding="utf-8") as f:
        fleet = FleetManager(RealityWorld.from_dict(json.load(f)))
    bridge = Bridge(mission.state(), fleet)
    tasks = bridge.materialize()
    print(f"2. Bridge: {len(tasks)} mission steps -> fleet tasks")

    # 3. REALITY: assign and execute.
    for task in fleet.assign_all():
        print(f"   assigned {task.name!r} -> {task.assigned_robot}")
    for task in tasks:
        fleet.complete_task(task.id, success=True)
        print(f"   completed {task.name!r}")

    # 4. Outcomes flow back to WORLD.
    rollup = bridge.sync_status()
    mission.update(
        {
            "status": "complete",
            "outcomes": [
                {
                    "task": t.name,
                    "robot": t.assigned_robot,
                    "status": t.status,
                }
                for t in tasks
            ],
        },
        actor="fleet-operator",
        note=f"fleet rollup: {rollup}",
    )
    mission.checkpoint("mission-complete")

    final = mission.state()
    print(
        f"3. WORLD: mission {final['status']!r}, "
        f"{len(final['outcomes'])} outcomes recorded"
    )
    for o in final["outcomes"]:
        print(f"   - {o['task']}: {o['status']} by {o['robot']}")
    print(f"   chain valid: {mission.verify()}")


if __name__ == "__main__":
    main()
