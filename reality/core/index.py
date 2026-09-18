"""Quadtree spatial index over entity positions.

The pipeline's SpatialIndex answers proximity queries by scanning every
entity — fine for office-sized worlds, wasteful past a few thousand
entities. Quadtree partitions the plane recursively so radius and bbox
queries only visit nodes that can contain hits.

The index stores entity ids with their positions; it does not own the
entities themselves. Rebuild it (or update/remove single entries) when
positions change — like any index, it is only as fresh as its last write.
"""

from __future__ import annotations

import math
from typing import Iterable

from reality.core.models import Point

Bounds = tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)


def bounds_for(points: Iterable[Point], pad: float = 1.0) -> Bounds:
    """Tight bounds around points, expanded by `pad` on every side."""
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    if not xs:
        raise ValueError("bounds_for() needs at least one point")
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def _bounds_intersect_circle(
    bounds: Bounds, center: Point, radius: float
) -> bool:
    closest_x = min(max(center.x, bounds[0]), bounds[2])
    closest_y = min(max(center.y, bounds[1]), bounds[3])
    return math.hypot(center.x - closest_x, center.y - closest_y) <= radius


def _bounds_intersect_bounds(a: Bounds, b: Bounds) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


class _Node:
    __slots__ = ("bounds", "capacity", "max_depth", "depth",
                 "points", "children")

    def __init__(self, bounds: Bounds, capacity: int,
                 max_depth: int, depth: int):
        self.bounds = bounds
        self.capacity = capacity
        self.max_depth = max_depth
        self.depth = depth
        self.points: list[tuple[str, Point]] = []
        self.children: list[_Node] | None = None

    def _subdivide(self) -> None:
        min_x, min_y, max_x, max_y = self.bounds
        mid_x, mid_y = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
        kw = dict(capacity=self.capacity, max_depth=self.max_depth,
                  depth=self.depth + 1)
        self.children = [
            _Node((min_x, min_y, mid_x, mid_y), **kw),  # SW
            _Node((mid_x, min_y, max_x, mid_y), **kw),  # SE
            _Node((min_x, mid_y, mid_x, max_y), **kw),  # NW
            _Node((mid_x, mid_y, max_x, max_y), **kw),  # NE
        ]
        points, self.points = self.points, []
        for entity_id, point in points:
            if not self._insert_into_children(entity_id, point):
                # Border point: no child claims it (half-open edges);
                # keep it at this level so it is never lost.
                self.points.append((entity_id, point))

    def _insert_into_children(self, entity_id: str, point: Point) -> bool:
        assert self.children is not None
        for child in self.children:
            if child._contains(point):
                child.insert(entity_id, point)
                return True
        return False

    def _contains(self, point: Point) -> bool:
        min_x, min_y, max_x, max_y = self.bounds
        # Half-open on the top/right edges so a point on a shared border
        # belongs to exactly one child.
        return (min_x <= point.x < max_x) and (min_y <= point.y < max_y)

    def insert(self, entity_id: str, point: Point) -> None:
        if self.children is not None:
            if not self._insert_into_children(entity_id, point):
                # On a degenerate border (zero-width bounds): keep it here.
                self.points.append((entity_id, point))
            return
        self.points.append((entity_id, point))
        if len(self.points) > self.capacity and self.depth < self.max_depth:
            self._subdivide()

    def remove(self, entity_id: str) -> bool:
        for i, (eid, _) in enumerate(self.points):
            if eid == entity_id:
                del self.points[i]
                return True
        if self.children is not None:
            return any(c.remove(entity_id) for c in self.children)
        return False

    def query_radius(
        self, center: Point, radius: float,
        out: list[tuple[str, float]],
    ) -> None:
        if not _bounds_intersect_circle(self.bounds, center, radius):
            return
        for entity_id, point in self.points:
            d = math.hypot(point.x - center.x, point.y - center.y)
            if d <= radius:
                out.append((entity_id, d))
        if self.children is not None:
            for child in self.children:
                child.query_radius(center, radius, out)

    def query_bbox(self, bbox: Bounds, out: list[str]) -> None:
        if not _bounds_intersect_bounds(self.bounds, bbox):
            return
        for entity_id, point in self.points:
            if (bbox[0] <= point.x <= bbox[2]
                    and bbox[1] <= point.y <= bbox[3]):
                out.append(entity_id)
        if self.children is not None:
            for child in self.children:
                child.query_bbox(bbox, out)

    def count_nodes(self) -> int:
        if self.children is None:
            return 1
        return 1 + sum(c.count_nodes() for c in self.children)


class Quadtree:
    """Point spatial index with radius and bounding-box queries.

    Usage:
        tree = Quadtree(bounds_for(points))
        for e in entities: tree.insert(e.id, e.position)
        hits = tree.query_radius(Point(x, y), radius)  # [(id, dist)]
    """

    def __init__(self, bounds: Bounds, capacity: int = 8,
                 max_depth: int = 16):
        min_x, min_y, max_x, max_y = bounds
        if not (min_x < max_x and min_y < max_y):
            raise ValueError(f"bounds must have positive area, got {bounds!r}")
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.bounds = bounds
        self._root = _Node(bounds, capacity, max_depth, depth=0)
        self._positions: dict[str, Point] = {}

    def __len__(self) -> int:
        return len(self._positions)

    def insert(self, entity_id: str, point: Point) -> None:
        """Insert (or re-insert) an entity position.

        Raises ValueError if the point is outside the tree bounds.
        """
        min_x, min_y, max_x, max_y = self.bounds
        if not (min_x <= point.x <= max_x and min_y <= point.y <= max_y):
            raise ValueError(
                f"point ({point.x}, {point.y}) outside tree bounds "
                f"{self.bounds!r}"
            )
        if entity_id in self._positions:
            self.remove(entity_id)
        self._root.insert(entity_id, point)
        self._positions[entity_id] = point

    def remove(self, entity_id: str) -> bool:
        """Remove an entity; returns True if it was present."""
        if entity_id not in self._positions:
            return False
        del self._positions[entity_id]
        return self._root.remove(entity_id)

    def update(self, entity_id: str, point: Point) -> None:
        """Move an entity to a new position (insert if unknown)."""
        self.insert(entity_id, point)

    def position_of(self, entity_id: str) -> Point | None:
        return self._positions.get(entity_id)

    def query_radius(self, center: Point, radius: float) -> list[tuple[str, float]]:
        """Entity ids within radius of center, sorted by distance."""
        if radius < 0:
            raise ValueError("radius must be non-negative")
        out: list[tuple[str, float]] = []
        self._root.query_radius(center, radius, out)
        out.sort(key=lambda h: h[1])
        return out

    def query_bbox(self, bbox: Bounds) -> list[str]:
        """Entity ids whose position falls inside bbox (edges count)."""
        out: list[str] = []
        self._root.query_bbox(bbox, out)
        return sorted(out)

    def node_count(self) -> int:
        return self._root.count_nodes()
