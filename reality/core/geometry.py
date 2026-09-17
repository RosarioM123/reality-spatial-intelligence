"""Pure-Python 2D geometry helpers (zones are modelled in x/y plane)."""

from __future__ import annotations

import math

from reality.core.models import Point

_EPS = 1e-9


def distance(a: Point, b: Point) -> float:
    """Euclidean distance in 3D."""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def distance_2d(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _point_on_segment(p: Point, a: Point, b: Point) -> bool:
    cross = (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)
    if abs(cross) > _EPS:
        return False
    dot = (p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y)
    if dot < -_EPS:
        return False
    sq_len = (b.x - a.x) ** 2 + (b.y - a.y) ** 2
    return dot <= sq_len + _EPS


def point_in_polygon(p: Point, polygon: list[Point]) -> bool:
    """Ray-casting point-in-polygon. Points on the boundary count as inside."""
    if len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        a, b = polygon[j], polygon[i]
        if _point_on_segment(p, a, b):
            return True
        if (a.y > p.y) != (b.y > p.y):
            x_inters = (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x
            if p.x < x_inters:
                inside = not inside
        j = i
    return inside


def polygon_area(polygon: list[Point]) -> float:
    """Shoelace formula (absolute area)."""
    area = 0.0
    n = len(polygon)
    for i in range(n):
        a, b = polygon[i], polygon[(i + 1) % n]
        area += a.x * b.y - b.x * a.y
    return abs(area) / 2.0


def bounding_box(polygon: list[Point]) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y)."""
    xs = [p.x for p in polygon]
    ys = [p.y for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def centroid(polygon: list[Point]) -> Point:
    """Area-weighted centroid of a polygon."""
    cx = cy = 0.0
    signed = 0.0
    n = len(polygon)
    for i in range(n):
        a, b = polygon[i], polygon[(i + 1) % n]
        cross = a.x * b.y - b.x * a.y
        signed += cross
        cx += (a.x + b.x) * cross
        cy += (a.y + b.y) * cross
    if abs(signed) < _EPS:
        # Degenerate: fall back to the arithmetic mean.
        return Point(
            sum(p.x for p in polygon) / n,
            sum(p.y for p in polygon) / n,
        )
    signed /= 2.0
    return Point(cx / (6.0 * signed), cy / (6.0 * signed))
