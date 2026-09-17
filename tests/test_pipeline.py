"""Pipeline tests: ingest, validation, locate, near, nearest, route."""

import json

import pytest

from reality.core.models import Point
from reality.core.pipeline import (
    SpatialPipeline,
    WorldValidationError,
    load_world,
)

OFFICE = "examples/office.json"


def _office():
    with open(OFFICE, encoding="utf-8") as f:
        return json.load(f)


def test_load_office_example():
    pipeline = SpatialPipeline.from_dict(_office())
    assert len(pipeline.world.zones) == 4
    assert len(pipeline.world.entities) == 5


def test_locate_zone():
    pipeline = SpatialPipeline.from_dict(_office())
    zone = pipeline.locate(Point(5, 4))
    assert zone is not None and zone.id == "lobby"
    zone = pipeline.locate(Point(12, 16))
    assert zone is not None and zone.id == "hallway"


def test_locate_outside_all_zones():
    pipeline = SpatialPipeline.from_dict(_office())
    assert pipeline.locate(Point(-5, -5)) is None


def test_near_sorted_by_distance():
    pipeline = SpatialPipeline.from_dict(_office())
    hits = pipeline.near(Point(5, 4), 10.0)
    assert hits[0]["entity"]["id"] == "reception-desk"
    assert hits[0]["distance"] == pytest.approx(0.0)
    distances = [h["distance"] for h in hits]
    assert distances == sorted(distances)


def test_near_with_kind_filter():
    pipeline = SpatialPipeline.from_dict(_office())
    hits = pipeline.near(Point(5, 4), 10.0, kind="equipment")
    ids = {h["entity"]["id"] for h in hits}
    assert ids == {"coffee-machine"}


def test_near_negative_radius_rejected():
    pipeline = SpatialPipeline.from_dict(_office())
    with pytest.raises(ValueError):
        pipeline.near(Point(0, 0), -1.0)


def test_nearest():
    pipeline = SpatialPipeline.from_dict(_office())
    hit = pipeline.nearest(Point(19, 14), kind="furniture")
    assert hit is not None
    assert hit["entity"]["id"] == "desk-1"


def test_nearest_unknown_kind_returns_none():
    pipeline = SpatialPipeline.from_dict(_office())
    assert pipeline.nearest(Point(0, 0), kind="spaceship") is None


def test_route_direct():
    pipeline = SpatialPipeline.from_dict(_office())
    assert pipeline.route("lobby", "hallway") == ["lobby", "hallway"]


def test_route_multi_hop():
    pipeline = SpatialPipeline.from_dict(_office())
    assert pipeline.route("office-a", "office-b") == [
        "office-a", "hallway", "office-b"]


def test_route_same_zone():
    pipeline = SpatialPipeline.from_dict(_office())
    assert pipeline.route("lobby", "lobby") == ["lobby"]


def test_route_unknown_zone_raises():
    pipeline = SpatialPipeline.from_dict(_office())
    with pytest.raises(KeyError):
        pipeline.route("lobby", "nowhere")


def test_route_disconnected_returns_none():
    data = _office()
    data["zones"].append({
        "id": "island", "name": "Island",
        "polygon": [[100, 100], [110, 100], [110, 110], [100, 110]],
    })
    pipeline = SpatialPipeline.from_dict(data)
    assert pipeline.route("lobby", "island") is None


def test_invalid_polygon_rejected():
    data = _office()
    data["zones"][0]["polygon"] = [[0, 0], [1, 1]]
    with pytest.raises(WorldValidationError):
        load_world(data)


def test_unknown_adjacency_rejected():
    data = _office()
    data["adjacency"]["lobby"].append("nowhere")
    with pytest.raises(WorldValidationError):
        load_world(data)


def test_entity_unknown_zone_rejected():
    data = _office()
    data["entities"][0]["zone_id"] = "nowhere"
    with pytest.raises(WorldValidationError):
        load_world(data)


def test_describe_zone():
    pipeline = SpatialPipeline.from_dict(_office())
    detail = pipeline.describe_zone("lobby")
    assert detail["area"] == pytest.approx(80.0)
    assert detail["connected_to"] == ["hallway"]
    assert {e["id"] for e in detail["entities"]} == {
        "reception-desk", "coffee-machine"}
