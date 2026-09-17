"""The spatial intelligence pipeline: ingest -> validate -> index -> query.

Stages:
  1. ingest: load a world description (dict or JSON file).
  2. validate: check ids, polygons, and adjacency references.
  3. index: build zone-containment and entity indexes.
  4. query: locate / near / nearest / route (see queries.py for NL access).
"""

from __future__ import annotations

import json
from collections import deque

from reality.core import geometry
from reality.core.models import Entity, Point, SpatialWorld, Zone


class WorldValidationError(ValueError):
    """Raised when a world description fails validation."""


def validate_world(world: SpatialWorld) -> list[str]:
    """Return a list of validation problems (empty means valid)."""
    problems: list[str] = []
    for zid, zone in world.zones.items():
        if len(zone.polygon) < 3:
            problems.append(f"zone {zid!r} has fewer than 3 polygon points")
        if geometry.polygon_area(zone.polygon) <= 0:
            problems.append(f"zone {zid!r} has zero polygon area")
    for zid, neighbours in world.adjacency.items():
        if zid not in world.zones:
            problems.append(f"adjacency references unknown zone {zid!r}")
        for n in neighbours:
            if n not in world.zones:
                problems.append(f"adjacency {zid!r} -> unknown zone {n!r}")
    for eid, entity in world.entities.items():
        if entity.zone_id is not None and entity.zone_id not in world.zones:
            problems.append(
                f"entity {eid!r} references unknown zone {entity.zone_id!r}"
            )
    return problems


def load_world(data: dict) -> SpatialWorld:
    """Build and validate a SpatialWorld from a plain dict."""
    world = SpatialWorld.from_dict(data)
    problems = validate_world(world)
    if problems:
        raise WorldValidationError("; ".join(problems))
    return world


def load_world_file(path: str) -> SpatialWorld:
    with open(path, encoding="utf-8") as f:
        return load_world(json.load(f))


class SpatialIndex:
    """In-memory indexes over a validated world."""

    def __init__(self, world: SpatialWorld):
        self.world = world
        # Precompute bounding boxes to skip most point-in-polygon tests.
        self._bboxes = {
            zid: geometry.bounding_box(z.polygon)
            for zid, z in world.zones.items()
        }

    def zone_at(self, p: Point) -> Zone | None:
        for zid, zone in self.world.zones.items():
            min_x, min_y, max_x, max_y = self._bboxes[zid]
            if not (min_x <= p.x <= max_x and min_y <= p.y <= max_y):
                continue
            if geometry.point_in_polygon(p, zone.polygon):
                return zone
        return None

    def entities_near(
        self, p: Point, radius: float, kind: str | None = None
    ) -> list[tuple[Entity, float]]:
        """Entities within radius of p, sorted by distance. Returns (entity, distance)."""
        if radius < 0:
            raise ValueError("radius must be non-negative")
        hits: list[tuple[Entity, float]] = []
        for entity in self.world.entities.values():
            if kind is not None and entity.kind != kind:
                continue
            d = geometry.distance(entity.position, p)
            if d <= radius:
                hits.append((entity, d))
        hits.sort(key=lambda h: h[1])
        return hits

    def nearest(self, p: Point, kind: str | None = None) -> tuple[Entity, float] | None:
        best: tuple[Entity, float] | None = None
        for entity in self.world.entities.values():
            if kind is not None and entity.kind != kind:
                continue
            d = geometry.distance(entity.position, p)
            if best is None or d < best[1]:
                best = (entity, d)
        return best


class SpatialPipeline:
    """End-to-end pipeline: holds a world, its index, and query methods."""

    def __init__(self, world: SpatialWorld):
        self.world = world
        self.index = SpatialIndex(world)

    @classmethod
    def from_dict(cls, data: dict) -> "SpatialPipeline":
        return cls(load_world(data))

    @classmethod
    def from_file(cls, path: str) -> "SpatialPipeline":
        return cls(load_world_file(path))

    # -- primitive queries -------------------------------------------------
    def locate(self, p: Point) -> Zone | None:
        """Which zone contains point p (or None)."""
        return self.index.zone_at(p)

    def near(
        self, p: Point, radius: float, kind: str | None = None, limit: int = 50
    ) -> list[dict]:
        hits = self.index.entities_near(p, radius, kind)[:limit]
        return [
            {"entity": e.to_dict(), "distance": round(d, 3)} for e, d in hits
        ]

    def nearest(self, p: Point, kind: str | None = None) -> dict | None:
        hit = self.index.nearest(p, kind)
        if hit is None:
            return None
        e, d = hit
        return {"entity": e.to_dict(), "distance": round(d, 3)}

    def route(self, from_zone_id: str, to_zone_id: str) -> list[str] | None:
        """Shortest zone path via the adjacency graph (BFS), or None."""
        if from_zone_id not in self.world.zones or to_zone_id not in self.world.zones:
            raise KeyError("unknown zone id in route()")
        if from_zone_id == to_zone_id:
            return [from_zone_id]
        prev: dict[str, str | None] = {from_zone_id: None}
        queue = deque([from_zone_id])
        while queue:
            current = queue.popleft()
            for nxt in self.world.adjacency.get(current, []):
                if nxt not in prev:
                    prev[nxt] = current
                    if nxt == to_zone_id:
                        path = [nxt]
                        while prev[path[-1]] is not None:
                            path.append(prev[path[-1]])  # type: ignore[arg-type]
                        return list(reversed(path))
                    queue.append(nxt)
        return None

    def describe_zone(self, zone_id: str) -> dict:
        zone = self.world.zones[zone_id]
        entities = [
            e.to_dict()
            for e in self.world.entities.values()
            if e.zone_id == zone_id
        ]
        return {
            "zone": zone.to_dict(),
            "area": round(geometry.polygon_area(zone.polygon), 3),
            "connected_to": sorted(self.world.adjacency.get(zone_id, [])),
            "entities": entities,
        }
