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
    if not polygon:
        raise ValueError("bounding_box() needs at least one point")
    xs = [p.x for p in polygon]
    ys = [p.y for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def bboxes_intersect(
    b1: tuple[float, float, float, float],
    b2: tuple[float, float, float, float],
) -> bool:
    """Do two (min_x, min_y, max_x, max_y) boxes overlap (edges count)?"""
    return not (b1[2] < b2[0] or b2[2] < b1[0] or b1[3] < b2[1] or b2[3] < b1[1])


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    """Do segments ab and cd intersect (touching counts)?"""
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if (o1 > _EPS) != (o2 > _EPS) and (o3 > _EPS) != (o4 > _EPS):
        return True
    # Collinear cases: an endpoint lying on the other segment counts.
    return (
        (abs(o1) <= _EPS and _point_on_segment(c, a, b))
        or (abs(o2) <= _EPS and _point_on_segment(d, a, b))
        or (abs(o3) <= _EPS and _point_on_segment(a, c, d))
        or (abs(o4) <= _EPS and _point_on_segment(b, c, d))
    )


def polygons_overlap(p1: list[Point], p2: list[Point]) -> bool:
    """Do two polygons overlap (share area or touch)?

    Fast path: bounding-box rejection. Then: any vertex of one inside the
    other, or any edge pair intersecting.
    """
    if len(p1) < 3 or len(p2) < 3:
        return False
    if not bboxes_intersect(bounding_box(p1), bounding_box(p2)):
        return False
    if any(point_in_polygon(p, p2) for p in p1):
        return True
    if any(point_in_polygon(p, p1) for p in p2):
        return True
    n, m = len(p1), len(p2)
    for i in range(n):
        a, b = p1[i], p1[(i + 1) % n]
        for j in range(m):
            c, d = p2[j], p2[(j + 1) % m]
            if segments_intersect(a, b, c, d):
                return True
    return False


def polygon_perimeter(polygon: list[Point]) -> float:
    """Closed-loop perimeter of a polygon."""
    n = len(polygon)
    if n < 2:
        return 0.0
    return sum(distance_2d(polygon[i], polygon[(i + 1) % n]) for i in range(n))


def centroid(polygon: list[Point]) -> Point:
    """Area-weighted centroid of a polygon."""
    if not polygon:
        raise ValueError("centroid() needs at least one point")
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
