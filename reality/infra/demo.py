"""The REALITY end-to-end demo: a deterministic simulated warehouse run.

Demonstrates the full loop the thesis is about:

  world state -> observation -> reasoning -> proposed action ->
  authorization -> execution -> observed result -> verified state

...plus the case the thesis exists for: the executor reports success,
the observation contradicts it, and verification catches the lie.

Run:  reality demo [world.json]      (default: examples/warehouse.json)
"""

from __future__ import annotations

import json

from reality.core.queries import ask_world
from reality.infra.simulation import Simulation


def _say(title: str) -> None:
    print(f"\n=== {title} ===")


def _kv(key: str, value) -> None:
    print(f"  {key}: {value}")


def run_demo(world_path: str) -> int:
    with open(world_path, encoding="utf-8") as f:
        data = json.load(f)
    sim = Simulation(data)
    world, engine = sim.world, sim.engine

    _say("1. Observe the warehouse (beliefs are born from observations)")
    sim.observe()
    _kv("entities observed", len(world.observations))
    _kv("events recorded", len(world.events))

    _say('2. Reason: "where is package p17?"')
    ans = ask_world(world, "where is package p17?")
    _kv("zone", ans["entity"]["zone_id"])
    _kv("status", ans["entity"]["state"].get("status"))
    _kv(
        "evidence source",
        ans["evidence"]["evidence"]["source"] if ans["evidence"] else None,
    )

    _say("3. Plan: propose moving p17 to storage-b (no approval yet)")
    sim.clock.tick()
    a1 = engine.propose(
        "move_entity", "demo-agent", "p17", {"to_zone": "storage-b"}, provenance="demo"
    )
    ok, msg = engine.authorize(a1)
    _kv("action", a1.id)
    _kv("authorized", ok)
    _kv("engine says", msg)

    _say("4. Authorize (human approval) -> execute -> observe -> verify")
    sim.clock.tick()
    ok, msg = engine.authorize(a1, approved_by="rosario")
    _kv("authorized", ok)
    sim.clock.tick()
    ok, msg = engine.execute(a1)
    _kv("executor report", f"{ok} ({msg})")
    sim.clock.tick()
    engine.ingest_observations(a1)
    result = engine.verify(a1)
    _kv("verification", result.status)
    _kv("p17 believed zone", world.get_attribute("p17", "zone_id"))

    _say('5. Reason again: "what changed?"')
    ans = ask_world(world, "what changed")
    for e in ans["events"][-4:]:
        print(f"  - [{e['type']}] {e['entity_id']}")

    _say("6. FAILURE CASE: executor lies, observation tells the truth")
    sim.clock.tick()
    a2 = engine.propose(
        "move_entity", "demo-agent", "p17", {"to_zone": "packing"}, provenance="demo"
    )
    # The executor will CLAIM success without moving anything.
    sim.add_fault(a2.id, "report_success_without_effect")
    engine.authorize(a2, approved_by="rosario")
    sim.clock.tick()
    ok, msg = engine.execute(a2)
    _kv("executor report", f"{ok} ({msg})")
    sim.clock.tick()
    engine.ingest_observations(a2)
    result2 = engine.verify(a2)
    _kv("verification", result2.status)
    for d in result2.discrepancies:
        print(f"  discrepancy: {d}")
    _kv("p17 believed zone", world.get_attribute("p17", "zone_id"))
    _kv("p17 actual zone", sim.ground_truth["p17"]["zone_id"])

    _say('7. Audit: "what evidence supports p17 being in storage-b?"')
    ans = ask_world(world, "what evidence supports p17 being in storage-b?")
    ev = ans["evidence"]
    _kv("consistent", ev["consistent"])
    _kv("source", ev["evidence"]["source"])
    _kv("confidence", ev["evidence"]["confidence"])

    _say("8. Full audit trail (JSON)")
    audit = {
        "actions": [a1.to_dict(), a2.to_dict()],
        "p17_history": world.history("p17"),
    }
    print(json.dumps(audit, indent=2)[:2000] + "\n  ... (truncated)")
    print(
        "\nDemo complete: 1 verified action, 1 failed verification "
        "(executor/observation discrepancy caught)."
    )
    return 0
