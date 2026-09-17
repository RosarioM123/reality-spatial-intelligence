"""Geometry unit tests."""

import math

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
