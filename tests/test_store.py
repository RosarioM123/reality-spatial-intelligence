"""Tests for the JSON persistence layer (reality/infra/store.py)."""

import json
import os

import pytest

from reality.core.models import SpatialWorld
from reality.core.pipeline import load_world
from reality.core.world import RealityWorld, WorldValidationError
from reality.infra.store import (
    JsonFileWorldStore,
    load_reality_world,
    load_world_path,
    save_world,
)

HERE = os.path.dirname(__file__)


def _load_example(name):
    with open(os.path.join(HERE, "..", "examples", name), encoding="utf-8") as f:
        return json.load(f)


def test_save_world_writes_json_and_returns_path(tmp_path):
    world = load_world(_load_example("warehouse.json"))
    path = str(tmp_path / "world.json")
    assert save_world(world, path) == path
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == world.to_dict()


def test_save_world_creates_missing_directories(tmp_path):
    world = load_world(_load_example("warehouse.json"))
    path = str(tmp_path / "nested" / "deep" / "world.json")
    save_world(world, path)
    assert os.path.exists(path)


def test_load_world_path_round_trip(tmp_path):
    world = load_world(_load_example("warehouse.json"))
    path = str(tmp_path / "world.json")
    save_world(world, path)
    reloaded = load_world_path(path)
    assert isinstance(reloaded, SpatialWorld)
    assert reloaded.to_dict() == world.to_dict()


def test_file_store_round_trip(tmp_path):
    store = JsonFileWorldStore()
    world = RealityWorld.from_dict(_load_example("fleet.json"))
    path = str(tmp_path / "reality.json")
    store.save(world, path)
    reloaded = store.load(path)
    assert isinstance(reloaded, RealityWorld)
    assert reloaded.to_dict() == world.to_dict()
    assert reloaded.validate() == []


def test_file_store_load_rejects_unknown_relationship_subject(tmp_path):
    data = _load_example("fleet.json")
    data["relationships"] = [
        {
            "subject_id": "ghost-entity",
            "predicate": "inside",
            "object_id": "depot",
            "provenance": None,
        }
    ]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data))
    with pytest.raises(WorldValidationError):
        JsonFileWorldStore().load(str(bad))


def test_load_reality_world_accepts_saved_file(tmp_path):
    store = JsonFileWorldStore()
    world = RealityWorld.from_dict(_load_example("fleet.json"))
    path = str(tmp_path / "reality.json")
    store.save(world, path)
    assert load_reality_world(path).validate() == []
