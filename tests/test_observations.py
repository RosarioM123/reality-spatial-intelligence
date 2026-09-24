"""Tests for contradictory-observation semantics."""

import pytest

from reality.core.models import Observation


def _obs(world, entity_id, state, ts, confidence=0.9, source="cam"):
    return Observation(
        id=world.new_id("obs"),
        ts=ts,
        source=source,
        entity_id=entity_id,
        observed_state=state,
        confidence=confidence,
    )


def test_high_confidence_contradiction_wins(observed_sim):
    world = observed_sim.world
    world.apply_observation(_obs(world, "p17", {"status": "packed"}, 2000.0))
    assert world.get_attribute("p17", "status") == "packed"


def test_low_confidence_contradiction_logs_conflict(observed_sim):
    world = observed_sim.world
    events = world.apply_observation(
        _obs(world, "p17", {"status": "shipped"}, 2000.0, confidence=0.2)
    )
    types = [e.type for e in events]
    assert "observation_conflict" in types
    # Low-confidence contradiction does not overwrite the believed state.
    assert world.get_attribute("p17", "status") == "intake"


def test_conflict_event_carries_evidence(observed_sim):
    world = observed_sim.world
    events = world.apply_observation(
        _obs(world, "p17", {"status": "shipped"}, 2000.0, confidence=0.2)
    )
    conflict = next(e for e in events if e.type == "observation_conflict")
    assert conflict.details["believed"] == "intake"
    assert conflict.details["reported"] == "shipped"
    assert conflict.details["believed_confidence"] == pytest.approx(0.95)
    assert conflict.details["reported_confidence"] == pytest.approx(0.2)
    assert conflict.details["observation_id"] is not None
    assert conflict.caused_by["kind"] == "observation"


def test_both_readings_are_kept(observed_sim):
    world = observed_sim.world
    n0 = len(world.observations)
    world.apply_observation(
        _obs(world, "p17", {"status": "shipped"}, 2000.0, confidence=0.2)
    )
    # Even a rejected reading stays in the record: nothing is silently lost.
    assert len(world.observations) == n0 + 1
