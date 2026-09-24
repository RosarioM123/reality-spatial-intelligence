"""Command-line interface for REALITY.

Spatial commands (work on any world file):
    validate, ask, route, near, zones

Action/state commands (world state engine):
    state <world> <entity>          believed state + provenance
    history <world> <entity>        temporal state transitions
    observe <world> [--save PATH]   run one simulated observation round
    act <world> <type> <target> [--param k=v] [--actor N] [--approve-as N] [--save PATH]
    verify-action <world> <action-id>
    demo [world]                    end-to-end warehouse demo (human-readable)

ask uses the full AI-native interface (ask_world): with a simulation runtime
attached, action questions like "move p17 to storage-b" run the complete
propose -> authorize -> execute -> observe -> verify loop.
"""

from __future__ import annotations

import argparse
import json
import sys

from reality import __version__
from reality.core.models import Point
from reality.core.pipeline import (
    SpatialPipeline,
    WorldValidationError,
    validate_world,
)
from reality.core.queries import ask_world
from reality.core.world import RealityWorld
from reality.infra.demo import run_demo
from reality.infra.simulation import Simulation
from reality.infra.store import JsonFileWorldStore, load_world_path


def _load_spatial(path: str) -> SpatialPipeline:
    try:
        return SpatialPipeline(load_world_path(path))
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001 -- CLI reports clean errors for any load failure
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


def _load_world(path: str) -> RealityWorld:
    """Load a reality/v0 world (accepts legacy spatial files too)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)
    world = RealityWorld.from_dict(data)
    problems = validate_world(world.spatial) + world.validate()
    if problems:
        print(f"error: invalid world {path}:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    return world


def _load_sim(path: str) -> Simulation:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        return Simulation(data)
    except WorldValidationError as exc:
        print(f"error: invalid world: {exc}", file=sys.stderr)
        sys.exit(1)


# -- spatial commands (unchanged behavior) ---------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    world = _load_world(args.world)
    problems = validate_world(world.spatial) + world.validate()
    if problems:
        print("invalid:")
        for p in problems:
            print(f"  - {p}")
        return 1
    n_conn = sum(len(v) for v in world.spatial.adjacency.values())
    print(
        f"valid: {len(world.spatial.zones)} zones, "
        f"{len(world.spatial.entities)} entities, {n_conn} connections, "
        f"{len(world.constraints)} constraints, "
        f"{len(world.relationships)} relationships"
    )
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    sim = _load_sim(args.world)
    sim.observe()  # a runtime's first job is to look at the world
    ans = ask_world(sim.world, args.question, runtime=sim, approved_by=args.approve_as)
    if args.format == "human":
        print(_render_human(ans))
    else:
        print(json.dumps(ans, indent=2))
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    pipeline = _load_spatial(args.world)
    try:
        path = pipeline.route(args.from_zone, args.to_zone)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if path is None:
        print(json.dumps({"route": None, "message": "no connected path between zones"}))
        return 1
    names = [pipeline.world.zones[z].name for z in path]
    print(json.dumps({"route": path, "names": names, "hops": len(path) - 1}, indent=2))
    return 0


def cmd_near(args: argparse.Namespace) -> int:
    pipeline = _load_spatial(args.world)
    hits = pipeline.near(Point(args.x, args.y), args.radius, kind=args.kind)
    print(json.dumps(hits, indent=2))
    return 0


def cmd_fleet(args: argparse.Namespace) -> int:
    from reality.core.fleet import FleetManager

    world = _load_world(args.world)
    fleet = FleetManager(world)
    status = fleet.fleet_status()
    print(f"fleet: {status['robot_count']} robots")
    for state, count in sorted(status["robots_by_status"].items()):
        print(f"  {state}: {count}")
    if status["tasks_by_status"]:
        print("tasks:")
        for state, count in sorted(status["tasks_by_status"].items()):
            print(f"  {state}: {count}")
    if status["low_battery"]:
        print(f"low battery: {', '.join(status['low_battery'])}")
    if args.detail:
        for robot in fleet.robots():
            s = fleet.robot_status(robot.id)
            caps = ", ".join(s["capabilities"])
            print(
                f"  {s['id']} ({s['name']}): {s['status']}, "
                f"battery {s['battery']}%, zone {s['zone_id']}, caps [{caps}]"
            )
    return 0


def cmd_zones(args: argparse.Namespace) -> int:
    pipeline = _load_spatial(args.world)
    for zid, zone in pipeline.world.zones.items():
        connected = ", ".join(sorted(pipeline.world.adjacency.get(zid, [])))
        print(
            f"{zid}: {zone.name} (floor {zone.floor})"
            + (f" -> {connected}" if connected else "")
        )
    return 0


# -- action/state commands ---------------------------------------------------


def cmd_state(args: argparse.Namespace) -> int:
    world = _load_world(args.world)
    entity = world.spatial.entities.get(args.entity)
    if entity is None:
        print(f"error: unknown entity {args.entity!r}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "id": entity.id,
                "name": entity.name,
                "kind": entity.kind,
                "zone_id": entity.zone_id,
                "position": entity.position.to_list(),
                "state": entity.state,
                "provenance": {
                    k: v.to_dict() for k, v in entity.state_provenance.items()
                },
            },
            indent=2,
        )
    )
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    world = _load_world(args.world)
    if args.entity not in world.spatial.entities:
        print(f"error: unknown entity {args.entity!r}", file=sys.stderr)
        return 1
    print(json.dumps(world.history(args.entity), indent=2))
    return 0


def cmd_observe(args: argparse.Namespace) -> int:
    sim = _load_sim(args.world)
    observations = sim.observe()
    if args.save:
        JsonFileWorldStore().save(sim.world, args.save)
    changed = [
        e
        for e in sim.world.events
        if e.type in ("state_changed", "observation_conflict")
    ]
    print(
        json.dumps(
            {
                "observations": len(observations),
                "state_changes": [e.to_dict() for e in changed],
            },
            indent=2,
        )
    )
    return 0


def cmd_act(args: argparse.Namespace) -> int:
    sim = _load_sim(args.world)
    params = {}
    for item in args.param or []:
        if "=" not in item:
            print(f"error: --param must be k=v, got {item!r}", file=sys.stderr)
            return 1
        k, v = item.split("=", 1)
        params[k] = v
    try:
        action = sim.engine.run(
            args.type,
            args.actor,
            args.target,
            params,
            approved_by=args.approve_as,
            provenance="cli",
        )
    except ValueError as exc:
        print(json.dumps({"type": "action_rejected", "reason": str(exc)}, indent=2))
        return 1
    if args.save:
        JsonFileWorldStore().save(sim.world, args.save)
    print(json.dumps(action.to_dict(), indent=2))
    return 0 if action.status not in ("failed", "rejected") else 1


def cmd_verify_action(args: argparse.Namespace) -> int:
    world = _load_world(args.world)
    action = world.actions.get(args.action_id)
    if action is None:
        print(f"error: unknown action {args.action_id!r}", file=sys.stderr)
        return 1
    print(json.dumps(action.to_dict(), indent=2))
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    return run_demo(args.world)


def cmd_to_geojson(args: argparse.Namespace) -> int:
    from reality.infra.geojson import world_to_geojson_str

    world = _load_world(args.world)
    text = world_to_geojson_str(world.spatial)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def cmd_from_geojson(args: argparse.Namespace) -> int:
    from reality.infra.geojson import load_geojson

    try:
        spatial = load_geojson(args.geojson)
    except Exception as exc:  # noqa: BLE001 -- CLI reports clean errors for any load failure
        print(f"error: {exc}", file=sys.stderr)
        return 1
    problems = validate_world(spatial)
    if problems:
        print("error: imported world is invalid:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    world = RealityWorld(spatial=spatial)
    world.snapshot_baseline()
    if args.out:
        JsonFileWorldStore().save(world, args.out)
        print(f"wrote {args.out}")
    else:
        print(f"valid: {len(spatial.zones)} zones, {len(spatial.entities)} entities")
    return 0


# -- human rendering ---------------------------------------------------------


def _render_human(ans: dict) -> str:
    t = ans.get("type")
    if t == "entity_location":
        e = ans["entity"]
        return (
            f"{e['name']} ({e['id']}) is in "
            f"{ans.get('zone_name') or ans.get('zone_id') or 'unknown zone'}. "
            f"State: {json.dumps(e.get('state', {}))}"
        )
    if t == "entity_status":
        e = ans["entity"]
        return (
            f"{e['name']}: {json.dumps(e.get('state', {}))} "
            f"[{len(ans.get('recent_changes', []))} recent changes]"
        )
    if t == "state_explanation":
        e = ans["entity"]
        lines = [f"{e['name']} state: {json.dumps(e.get('state', {}))}"]
        for h in ans.get("history", [])[-3:]:
            lines.append(f"  - {h['attribute']}: {h['old']} -> {h['new']}")
        return "\n".join(lines)
    if t == "changes":
        lines = [f"{ans['count']} events:"]
        for e in ans.get("events", [])[-8:]:
            lines.append(f"  - [{e['type']}] {e.get('entity_id')}")
        return "\n".join(lines)
    if t == "history":
        lines = [f"history of {ans['entity_id']}:"]
        for h in ans.get("transitions", []):
            lines.append(f"  - {h['attribute']}: {h['old']} -> {h['new']}")
        return "\n".join(lines) or "no recorded transitions"
    if t == "evidence":
        ev = ans["evidence"] or {}
        sub = ev.get("evidence") or {}
        return (
            f"Belief: {ev.get('entity_id')}.{ev.get('attribute')} = "
            f"{ev.get('value')!r} (consistent with claim: "
            f"{ev.get('consistent')}). Source: {sub.get('source')}, "
            f"confidence {sub.get('confidence')}, "
            f"observation {sub.get('observation_id')}."
        )
    if t == "capabilities":
        lines = ["Available actions:"]
        for a in ans.get("available", []):
            lines.append(
                f"  - {a['action']} on {a['entity_id']} "
                f"(params: {', '.join(a['params']) or 'none'})"
            )
        return "\n".join(lines) or "no actions available"
    if t == "action_plan":
        steps = ans.get("plan", [])
        lines = ["Plan (not executed):"]
        for s in steps:
            lines.append(f"  - {s['action']} {s['target']} {s['parameters']}")
        if ans.get("note"):
            lines.append(ans["note"])
        return "\n".join(lines)
    if t == "action_result":
        a = ans["action"]
        v = (a.get("verification") or {}).get("status")
        out = [
            f"Action {a['id']} ({a['type']} on {a['target']}): "
            f"{a['status']}" + (f" (verification: {v})" if v else "")
        ]
        for d in (a.get("verification") or {}).get("discrepancies", []):
            out.append(f"  discrepancy: {d}")
        return "\n".join(out)
    if t == "action_status":
        a = ans["action"]
        return f"Action {a['id']}: {a['status']}"
    if t == "action_rejected":
        return f"Action rejected: {ans.get('reason')}"
    if t == "workstation_plan":
        lines = [
            (
                f"Chosen: {ans['chosen']['name']} "
                f"({ans['chosen']['id']}, {ans['distance_to_team']}m from "
                f"{ans['team']})"
            )
        ]
        for s in ans["plan"]:
            blocked = " BLOCKED" if s.get("blocked") else ""
            lines.append(f"  - {s['action']} {s['target']}{blocked}")
        for ex in ans.get("execution", []) or []:
            if isinstance(ex, dict) and "status" in ex:
                lines.append(f"  executed {ex['id']}: {ex['status']}")
        return "\n".join(lines)
    if t == "not_found":
        return ans.get("message", "not found")
    if t == "no_workstation":
        return ans.get("message", "no workstation available")
    if t == "unrecognized":
        return ans.get("message", "could not parse") + ". " + ans.get("hint", "")
    return json.dumps(ans, indent=2)


# -- parser --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reality",
        description="REALITY: action/state layer for AI in the physical world",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validate a world JSON file")
    p.add_argument("world")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("ask", help="ask anything in plain language")
    p.add_argument("world")
    p.add_argument("question")
    p.add_argument("--format", choices=["json", "human"], default="json")
    p.add_argument(
        "--approve-as", default=None, help="run actions under this approver's authority"
    )
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("route", help="shortest zone path between two zones")
    p.add_argument("world")
    p.add_argument("from_zone")
    p.add_argument("to_zone")
    p.set_defaults(func=cmd_route)

    p = sub.add_parser("near", help="entities within a radius of a point")
    p.add_argument("world")
    p.add_argument("x", type=float)
    p.add_argument("y", type=float)
    p.add_argument("radius", type=float)
    p.add_argument("--kind", default=None)
    p.set_defaults(func=cmd_near)

    p = sub.add_parser("zones", help="list zones and their connections")
    p.add_argument("world")
    p.set_defaults(func=cmd_zones)

    p = sub.add_parser("fleet", help="fleet status: robots, tasks, battery")
    p.add_argument("world")
    p.add_argument("--detail", action="store_true", help="per-robot breakdown")
    p.set_defaults(func=cmd_fleet)

    p = sub.add_parser("state", help="believed state + provenance of an entity")
    p.add_argument("world")
    p.add_argument("entity")
    p.set_defaults(func=cmd_state)

    p = sub.add_parser("history", help="state transitions of an entity")
    p.add_argument("world")
    p.add_argument("entity")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("observe", help="run one simulated observation round")
    p.add_argument("world")
    p.add_argument("--save", default=None)
    p.set_defaults(func=cmd_observe)

    p = sub.add_parser("act", help="run the full action lifecycle")
    p.add_argument("world")
    p.add_argument(
        "type",
        help="move_entity, reserve_resource, change_status, assign_entity, notify",
    )
    p.add_argument("target", help="entity id")
    p.add_argument(
        "--param",
        action="append",
        default=[],
        help="action parameter as k=v (repeatable)",
    )
    p.add_argument("--actor", default="cli")
    p.add_argument("--approve-as", default=None)
    p.add_argument("--save", default=None)
    p.set_defaults(func=cmd_act)

    p = sub.add_parser("verify-action", help="show an action record")
    p.add_argument("world")
    p.add_argument("action_id")
    p.set_defaults(func=cmd_verify_action)

    p = sub.add_parser("demo", help="end-to-end warehouse demo")
    p.add_argument("world", nargs="?", default="examples/warehouse.json")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("to-geojson", help="export the spatial substrate as GeoJSON")
    p.add_argument("world")
    p.add_argument("--out", default=None, help="write to this file instead of stdout")
    p.set_defaults(func=cmd_to_geojson)

    p = sub.add_parser(
        "from-geojson", help="import a GeoJSON FeatureCollection as a world"
    )
    p.add_argument("geojson")
    p.add_argument(
        "--out", default=None, help="save the imported world to this JSON file"
    )
    p.set_defaults(func=cmd_from_geojson)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
