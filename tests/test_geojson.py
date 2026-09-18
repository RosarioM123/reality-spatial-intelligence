"""GeoJSON import/export tests."""

import json
import os
import tempfile

import pytest

from reality.core.models import Entity, Point, SpatialWorld, Zone
from reality.infra.geojson import (
    GeoJSONError,
    geojson_to_world,
    geojson_to_world_str,
    load_geojson,
    save_geojson,
    world_to_geojson,
    world_to_geojson_str,
)


def _world():
    return SpatialWorld(
        zones={
            "a": Zone(id="a", name="Room A",
                      polygon=[Point(0, 0), Point(10, 0), Point(10, 10),
                               Point(0, 10)],
                      floor=1, properties={"wing": "east"}),
        },
        entities={
            "e1": Entity(id="e1", name="Sensor 1", kind="sensor",
                         position=Point(5, 5, 2.5), zone_id="a",
                         state={"status": "ok"}),
        },
        adjacency={"a": []},
    )


def test_round_trip_preserves_world():
    world = _world()
    back = geojson_to_world(world_to_geojson(world))
    assert set(back.zones) == {"a"}
    zone = back.zones["a"]
    assert zone.name == "Room A" and zone.floor == 1
    assert zone.properties == {"wing": "east"}
    assert [(p.x, p.y) for p in zone.polygon] == \
        [(0, 0), (10, 0), (10, 10), (0, 10)]
    entity = back.entities["e1"]
    assert entity.name == "Sensor 1" and entity.kind == "sensor"
    assert entity.position == Point(5, 5, 2.5)  # z survives
    assert entity.zone_id == "a" and entity.state == {"status": "ok"}
    assert back.adjacency == {"a": []}


def test_ring_is_closed_and_valid_geojson():
    fc = world_to_geojson(_world())
    assert fc["type"] == "FeatureCollection"
    zone_feat = next(f for f in fc["features"]
                     if f["properties"]["kind"] == "zone")
    ring = zone_feat["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]  # GeoJSON rings are closed
    assert len(ring) == 5
    # 2D positions stay 2D ...
    assert all(len(pos) == 2 for pos in ring)
    # ... while a nonzero z is kept.
    ent_feat = next(f for f in fc["features"]
                    if f["properties"]["kind"] == "entity")
    assert ent_feat["geometry"]["coordinates"] == [5, 5, 2.5]


def test_round_trip_office_example(office_data):
    world = SpatialWorld.from_dict(
        {"zones": office_data["zones"], "entities": office_data["entities"],
         "adjacency": office_data.get("adjacency", {})})
    back = geojson_to_world(world_to_geojson(world))
    assert set(back.zones) == set(world.zones)
    assert set(back.entities) == set(world.entities)
    assert back.adjacency == world.adjacency
    for zid, zone in world.zones.items():
        assert len(back.zones[zid].polygon) == len(zone.polygon)
        for p, q in zip(back.zones[zid].polygon, zone.polygon):
            assert (p.x, p.y, p.z) == (q.x, q.y, q.z)


def test_save_and_load_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "world.geojson")
        save_geojson(_world(), path)
        # The file is plain GeoJSON any GIS tool can open.
        raw = json.load(open(path, encoding="utf-8"))
        assert raw["type"] == "FeatureCollection"
        back = load_geojson(path)
        assert set(back.zones) == {"a"}


def test_rejects_malformed_input():
    with pytest.raises(GeoJSONError):
        geojson_to_world({"type": "Feature"})  # wrong type
    with pytest.raises(GeoJSONError):
        geojson_to_world({"type": "FeatureCollection"})  # no features
    with pytest.raises(GeoJSONError):
        geojson_to_world_str("{not json")
    with pytest.raises(GeoJSONError):
        geojson_to_world({"type": "FeatureCollection", "features": [
            {"type": "Feature",
             "geometry": {"type": "LineString",
                          "coordinates": [[0, 0], [1, 1]]},
             "properties": {"kind": "zone", "id": "z"}}]})  # not Polygon


def test_rejects_duplicate_ids():
    feat = {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [1, 2]},
            "properties": {"kind": "entity", "id": "e1"}}
    with pytest.raises(GeoJSONError):
        geojson_to_world({"type": "FeatureCollection",
                          "features": [feat, feat]})


def test_rejects_bad_coordinates():
    feat = {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": ["x", 2]},
            "properties": {"kind": "entity", "id": "e1"}}
    with pytest.raises(GeoJSONError):
        geojson_to_world({"type": "FeatureCollection", "features": [feat]})
    thin = {"type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [[[0, 0], [1, 1], [0, 0]]]},
            "properties": {"kind": "zone", "id": "z"}}
    with pytest.raises(GeoJSONError):
        geojson_to_world({"type": "FeatureCollection", "features": [thin]})


def test_open_ring_is_closed_on_import():
    feat = {"type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [[[0, 0], [10, 0], [10, 10],
                                          [0, 10]]]},
            "properties": {"kind": "zone", "id": "z", "name": "Z"}}
    world = geojson_to_world(
        {"type": "FeatureCollection", "features": [feat]})
    assert len(world.zones["z"].polygon) == 4
