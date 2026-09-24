"""Quadtree index tests, including a brute-force benchmark."""

import random
import time

import pytest

from reality.core.index import Quadtree, bounds_for
from reality.core.models import Point


def _grid_points(n=25, spacing=10.0):
    pts = []
    for i in range(n):
        for j in range(n):
            pts.append(Point(i * spacing, j * spacing))
    return pts


def test_insert_and_query_radius():
    pts = _grid_points()
    tree = Quadtree(bounds_for(pts))
    for k, p in enumerate(pts):
        tree.insert(f"e{k}", p)
    assert len(tree) == len(pts)
    hits = tree.query_radius(Point(0, 0), 10.0)
    ids = {eid for eid, _ in hits}
    # (0,0), (10,0), (0,10): the diagonal (10,10) is ~14.14 away.
    assert ids == {"e0", "e1", "e25"}
    dists = [d for _, d in hits]
    assert dists == sorted(dists)


def test_query_bbox():
    pts = _grid_points()
    tree = Quadtree(bounds_for(pts))
    for k, p in enumerate(pts):
        tree.insert(f"e{k}", p)
    ids = set(tree.query_bbox((0, 0, 10, 10)))
    assert ids == {"e0", "e1", "e25", "e26"}


def test_border_points_are_never_lost():
    # Points exactly on subdivision borders must stay queryable.
    pts = [
        Point(0, 0),
        Point(50, 0),
        Point(100, 0),
        Point(0, 50),
        Point(50, 50),
        Point(100, 50),
    ]
    tree = Quadtree((0, 0, 100, 50), capacity=1)
    for k, p in enumerate(pts):
        tree.insert(f"e{k}", p)
    hits = tree.query_radius(Point(50, 25), 1000.0)
    assert {eid for eid, _ in hits} == {f"e{k}" for k in range(len(pts))}


def test_remove_and_update():
    tree = Quadtree((0, 0, 100, 100))
    tree.insert("a", Point(10, 10))
    tree.insert("b", Point(90, 90))
    assert tree.remove("a")
    assert not tree.remove("a")
    assert len(tree) == 1
    assert tree.query_radius(Point(10, 10), 5.0) == []
    tree.update("b", Point(12, 12))
    hits = tree.query_radius(Point(10, 10), 5.0)
    assert [eid for eid, _ in hits] == ["b"]
    assert tree.position_of("b") == Point(12, 12)
    assert tree.position_of("missing") is None


def test_out_of_bounds_rejected():
    tree = Quadtree((0, 0, 10, 10))
    with pytest.raises(ValueError):
        tree.insert("x", Point(11, 5))
    with pytest.raises(ValueError):
        Quadtree((0, 0, 0, 10))
    with pytest.raises(ValueError):
        tree.query_radius(Point(5, 5), -1.0)
    with pytest.raises(ValueError):
        bounds_for([])


def test_reinsert_replaces_position():
    tree = Quadtree((0, 0, 100, 100))
    tree.insert("a", Point(10, 10))
    tree.insert("a", Point(80, 80))  # re-insert moves it
    assert len(tree) == 1
    assert tree.query_radius(Point(10, 10), 5.0) == []
    assert [eid for eid, _ in tree.query_radius(Point(80, 80), 5.0)] == ["a"]


def test_matches_brute_force():
    rng = random.Random(42)
    pts = [Point(rng.uniform(0, 500), rng.uniform(0, 500)) for _ in range(500)]
    tree = Quadtree(bounds_for(pts))
    for k, p in enumerate(pts):
        tree.insert(f"e{k}", p)
    for _ in range(20):
        c = Point(rng.uniform(0, 500), rng.uniform(0, 500))
        r = rng.uniform(1, 60)
        got = {eid for eid, _ in tree.query_radius(c, r)}
        want = {
            f"e{k}"
            for k, p in enumerate(pts)
            if (p.x - c.x) ** 2 + (p.y - c.y) ** 2 <= r**2
        }
        assert got == want


def test_quadtree_beats_brute_force():
    """Benchmark: indexed radius queries beat a full scan on 3000 entities."""
    rng = random.Random(7)
    pts = [Point(rng.uniform(0, 1000), rng.uniform(0, 1000)) for _ in range(3000)]
    tree = Quadtree(bounds_for(pts))
    for k, p in enumerate(pts):
        tree.insert(f"e{k}", p)
    queries = [
        (Point(rng.uniform(0, 1000), rng.uniform(0, 1000)), rng.uniform(5, 40))
        for _ in range(100)
    ]

    def brute(center, radius):
        r2 = radius**2
        return sorted(
            eid
            for eid, p in enumerate(pts)
            if (p.x - center.x) ** 2 + (p.y - center.y) ** 2 <= r2
        )

    t0 = time.perf_counter()
    for c, r in queries:
        [eid for eid, _ in tree.query_radius(c, r)]
    qt_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    for c, r in queries:
        brute(c, r)
    brute_time = time.perf_counter() - t0

    # Correctness on the benchmark queries too.
    for c, r in queries[:10]:
        assert {eid for eid, _ in tree.query_radius(c, r)} == {
            f"e{e}" for e in brute(c, r)
        }

    assert qt_time < brute_time, (
        f"quadtree ({qt_time:.3f}s) not faster than brute force ({brute_time:.3f}s)"
    )
