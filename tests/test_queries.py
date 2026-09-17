"""Tests for the natural-language query layer and the JSON store."""

import json
import os

import pytest

from reality.core.pipeline import SpatialPipeline
from reality.core.queries import ask
from reality.infra.store import load_world_path, save_world

OFFICE = "examples/office.json"


@pytest.fixture()
def pipeline():
    with open(OFFICE, encoding="utf-8") as f:
        return SpatialPipeline.from_dict(json.load(f))


def test_ask_where_is(pipeline):
    ans = ask(pipeline, "where is printer-1?")
    assert ans["type"] == "entity_location"
    assert ans["zone_id"] == "hallway"
    assert ans["entity"]["position"] == {"x": 12.0, "y": 16.0, "z": 0.0}


def test_ask_where_is_unknown(pipeline):
    ans = ask(pipeline, "where is the batcave")
    assert ans["type"] == "not_found"


def test_ask_what_is_near(pipeline):
    ans = ask(pipeline, "what is near reception-desk within 5")
    assert ans["type"] == "nearby"
    ids = [h["entity"]["id"] for h in ans["results"]]
    assert "coffee-machine" in ids
    assert "reception-desk" not in ids  # origin excluded


def test_ask_nearest_kind_to_entity(pipeline):
    ans = ask(pipeline, "nearest equipment to desk-1")
    assert ans["type"] == "nearest"
    assert ans["result"]["entity"]["id"] == "printer-1"


def test_ask_route(pipeline):
    ans = ask(pipeline, "how do I get from Office A to Office B?")
    assert ans["type"] == "route"
    assert ans["path"] == ["office-a", "hallway", "office-b"]
    assert ans["hops"] == 2


def test_ask_zone_at_point(pipeline):
    ans = ask(pipeline, "what zone is at (2, 7)?")
    assert ans["type"] == "zone_at"
    assert ans["zone_id"] == "lobby"


def test_ask_zone_at_point_outside(pipeline):
    ans = ask(pipeline, "what zone is at (99, 99)?")
    assert ans["type"] == "no_zone"


def test_ask_list_zones(pipeline):
    ans = ask(pipeline, "list zones")
    assert ans["type"] == "zone_list"
    assert len(ans["zones"]) == 4


def test_ask_list_entities_of_kind(pipeline):
    ans = ask(pipeline, "list entities of kind sensor")
    assert ans["type"] == "entity_list"
    assert [e["id"] for e in ans["entities"]] == ["sensor-temp-1"]


def test_ask_describe_zone(pipeline):
    ans = ask(pipeline, "describe lobby")
    assert ans["type"] == "zone_detail"
    assert ans["detail"]["zone"]["id"] == "lobby"


def test_ask_unrecognized(pipeline):
    ans = ask(pipeline, "tell me a joke")
    assert ans["type"] == "unrecognized"
    assert "hint" in ans


def test_answers_are_json_serializable(pipeline):
    questions = [
        "where is printer-1",
        "what is near reception-desk",
        "nearest sensor to desk-1",
        "route from lobby to office-a",
        "what zone is at (2, 7)",
        "list zones",
        "describe hallway",
    ]
    for q in questions:
        json.dumps(ask(pipeline, q))  # must not raise


def test_store_round_trip(pipeline, tmp_path):
    path = str(tmp_path / "world.json")
    save_world(pipeline.world, path)
    assert os.path.exists(path)
    world2 = load_world_path(path)
    assert set(world2.zones) == set(pipeline.world.zones)
    assert set(world2.entities) == set(pipeline.world.entities)
    assert world2.adjacency == pipeline.world.adjacency
    assert world2.entities["printer-1"].position.x == 12.0
