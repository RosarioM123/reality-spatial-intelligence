"""Geometry unit tests."""

import pytest

from reality.core.geometry import (
    bounding_box,
    centroid,
    distance,
    point_in_polygon,
    polygon_area,
)
from reality.core.models import Point

SQUARE = [Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)]


def test_point_inside_square():
    assert point_in_polygon(Point(5, 5), SQUARE)


def test_point_outside_square():
    assert not point_in_polygon(Point(15, 5), SQUARE)


def test_point_on_boundary_counts_as_inside():
    assert point_in_polygon(Point(0, 5), SQUARE)
    assert point_in_polygon(Point(5, 0), SQUARE)
    assert point_in_polygon(Point(10, 10), SQUARE)


def test_concave_polygon():
    # Arrow / chevron shape; notch at (5, 5).
    poly = [Point(0, 0), Point(10, 0), Point(10, 10), Point(5, 5), Point(0, 10)]
    assert point_in_polygon(Point(2, 2), poly)
    assert not point_in_polygon(Point(5, 8), poly)


def test_polygon_area():
    assert polygon_area(SQUARE) == pytest.approx(100.0)
    tri = [Point(0, 0), Point(4, 0), Point(0, 3)]
    assert polygon_area(tri) == pytest.approx(6.0)


def test_bounding_box():
    assert bounding_box(SQUARE) == (0, 0, 10, 10)


def test_centroid_of_square():
    c = centroid(SQUARE)
    assert c.x == pytest.approx(5.0)
    assert c.y == pytest.approx(5.0)


def test_distance_3d():
    assert distance(Point(0, 0, 0), Point(1, 2, 2)) == pytest.approx(3.0)


def test_degenerate_polygon_is_not_container():
    assert not point_in_polygon(Point(0, 0), [Point(0, 0), Point(1, 1)])


# -- polygon ops added for the visualizer / geofence work --------------------

from reality.core.geometry import (
    bboxes_intersect,
    polygon_perimeter,
    polygons_overlap,
    segments_intersect,
)


def test_bboxes_intersect():
    assert bboxes_intersect((0, 0, 10, 10), (5, 5, 15, 15))
    assert bboxes_intersect((0, 0, 10, 10), (10, 0, 20, 10))  # touching edge
    assert not bboxes_intersect((0, 0, 10, 10), (11, 0, 20, 10))
    assert not bboxes_intersect((0, 0, 10, 10), (0, 11, 10, 20))


def test_segments_intersect():
    a, b = Point(0, 0), Point(10, 10)
    assert segments_intersect(a, b, Point(0, 10), Point(10, 0))
    assert not segments_intersect(a, b, Point(20, 20), Point(30, 30))
    # Touching at an endpoint counts.
    assert segments_intersect(a, b, Point(10, 10), Point(20, 10))
    # Collinear overlap counts.
    assert segments_intersect(a, b, Point(5, 5), Point(15, 15))
    # Collinear but disjoint does not.
    assert not segments_intersect(a, b, Point(11, 11), Point(20, 20))


def test_polygons_overlap():
    other = [Point(5, 5), Point(15, 5), Point(15, 15), Point(5, 15)]
    assert polygons_overlap(SQUARE, other)
    far = [Point(50, 50), Point(60, 50), Point(60, 60), Point(50, 60)]
    assert not polygons_overlap(SQUARE, far)
    # Touching at an edge counts as overlap.
    touching = [Point(10, 0), Point(20, 0), Point(20, 10), Point(10, 10)]
    assert polygons_overlap(SQUARE, touching)
    # One fully inside the other.
    inner = [Point(2, 2), Point(4, 2), Point(4, 4), Point(2, 4)]
    assert polygons_overlap(SQUARE, inner)
    # Degenerate input never overlaps.
    assert not polygons_overlap(SQUARE, [Point(0, 0), Point(1, 1)])


def test_polygon_perimeter():
    assert polygon_perimeter(SQUARE) == pytest.approx(40.0)
    tri = [Point(0, 0), Point(3, 0), Point(0, 4)]
    assert polygon_perimeter(tri) == pytest.approx(12.0)
    assert polygon_perimeter([]) == 0.0
    assert polygon_perimeter([Point(1, 1)]) == 0.0


def test_empty_polygon_guards():
    with pytest.raises(ValueError):
        bounding_box([])
    with pytest.raises(ValueError):
        centroid([])
