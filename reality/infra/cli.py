"""Command-line interface for the reality spatial pipeline.

Usage:
    python -m reality.infra.cli validate <world.json>
    python -m reality.infra.cli ask <world.json> "<question>"
    python -m reality.infra.cli route <world.json> <from-zone> <to-zone>
    python -m reality.infra.cli near <world.json> <x> <y> <radius> [--kind KIND]
    python -m reality.infra.cli zones <world.json>
"""

from __future__ import annotations

import argparse
import json
import sys

from reality.core.models import Point
from reality.core.pipeline import SpatialPipeline, validate_world
from reality.core.queries import ask
from reality.infra.store import load_world_path


def _load(path: str) -> SpatialPipeline:
    try:
        return SpatialPipeline(load_world_path(path))
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # validation / JSON errors
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_validate(args: argparse.Namespace) -> int:
    world = load_world_path(args.world)
    problems = validate_world(world)
    if problems:
        print("invalid:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"valid: {len(world.zones)} zones, {len(world.entities)} entities, "
          f"{sum(len(v) for v in world.adjacency.values())} connections")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    pipeline = _load(args.world)
    print(json.dumps(ask(pipeline, args.question), indent=2))
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    pipeline = _load(args.world)
    try:
        path = pipeline.route(args.from_zone, args.to_zone)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if path is None:
        print(json.dumps({"route": None,
                          "message": "no connected path between zones"}))
        return 1
    names = [pipeline.world.zones[z].name for z in path]
    print(json.dumps({"route": path, "names": names,
                      "hops": len(path) - 1}, indent=2))
    return 0


def cmd_near(args: argparse.Namespace) -> int:
    pipeline = _load(args.world)
    hits = pipeline.near(Point(args.x, args.y), args.radius, kind=args.kind)
    print(json.dumps(hits, indent=2))
    return 0


def cmd_zones(args: argparse.Namespace) -> int:
    pipeline = _load(args.world)
    for zid, zone in pipeline.world.zones.items():
        connected = ", ".join(sorted(pipeline.world.adjacency.get(zid, [])))
        print(f"{zid}: {zone.name} (floor {zone.floor})"
              + (f" -> {connected}" if connected else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reality", description="AI-native spatial intelligence pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validate a world JSON file")
    p.add_argument("world")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("ask", help="ask a spatial question in plain language")
    p.add_argument("world")
    p.add_argument("question")
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
