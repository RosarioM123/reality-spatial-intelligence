"""Tests for the world state engine: observations -> believed state."""

import pytest

from reality.core.models import Observation
from reality.core.world import RealityWorld


def _obs(
    world, entity_id, state, ts=1000.0, source="test-cam", confidence=0.9, oid=None
):
    return Observation(
        id=oid or world.new_id("obs"),
        ts=ts,
        source=source,
        entity_id=entity_id,
        observed_state=state,
        confidence=confidence,
    )


def test_observation_establishes_belief(observed_sim):
    world = observed_sim.world
    assert world.get_attribute("p17", "zone_id") == "storage-a"
    assert world.get_attribute("p17", "status") == "intake"
    prov = world.get_provenance("p17", "status")
    assert prov is not None
    assert prov.source == "sim-camera-1"
    assert prov.confidence == pytest.approx(0.95)
    assert prov.observation_id is not None


def test_observation_for_unknown_entity_logs_event(observed_sim):
    world = observed_sim.world
    events = world.apply_observation(_obs(world, "ghost", {"status": "x"}))
    types = [e.type for e in events]
    assert "observation_recorded" in types
    assert "observation_for_unknown_entity" in types


def test_state_change_event_records_old_and_new(observed_sim):
    world = observed_sim.world
    before = len(world.events)
    world.apply_observation(_obs(world, "p17", {"status": "packed"}, ts=2000.0))
    changes = [e for e in world.events[before:] if e.type == "state_changed"]
    assert len(changes) == 1
    assert changes[0].details["attribute"] == "status"
    assert changes[0].details["old"] == "intake"
    assert changes[0].details["new"] == "packed"
    assert changes[0].caused_by["kind"] == "observation"


def test_location_update_via_observation(observed_sim):
    world = observed_sim.world
    world.apply_observation(_obs(world, "p17", {"zone_id": "packing"}, ts=2000.0))
    assert world.get_attribute("p17", "zone_id") == "packing"
    prov = world.get_provenance("p17", "zone_id")
    assert prov.source == "test-cam"


def test_no_event_when_nothing_changed(observed_sim):
    world = observed_sim.world
    before = len(world.events)
    world.apply_observation(_obs(world, "p17", {"status": "intake"}, ts=2000.0))
    new = world.events[before:]
    assert [e.type for e in new] == ["observation_recorded"]


def test_actions_do_not_directly_mutate_belief(observed_sim):
    """The epistemic rule: executing an action never writes believed state."""
    sim = observed_sim
    world = sim.world
    # Move ground truth directly, bypassing observation.
    sim.ground_truth["p17"]["zone_id"] = "shipping"
    assert world.get_attribute("p17", "zone_id") == "storage-a"
    # Only an observation updates belief.
    sim.observe()
    assert world.get_attribute("p17", "zone_id") == "shipping"


def test_world_validation_catches_bad_relationship(observed_sim):
    from reality.core.models import Relationship

    world = observed_sim.world
    world.relationships.append(Relationship("p17", "inside", "no-such-zone"))
    problems = world.validate()
    assert any("no-such-zone" in p for p in problems)


def test_world_serialization_round_trip(observed_sim):
    world = observed_sim.world
    data = world.to_dict()
    restored = RealityWorld.from_dict(data)
    assert restored.get_attribute("p17", "status") == "intake"
    assert len(restored.events) == len(world.events)
    assert len(restored.observations) == len(world.observations)
    assert restored.constraints[0].id == world.constraints[0].id
