"""Tests for temporal awareness: history, state_at, what_changed, evidence."""

from reality.core.models import Observation


def _obs(world, entity_id, state, ts, source="test-cam", confidence=0.9):
    return Observation(
        id=world.new_id("obs"),
        ts=ts,
        source=source,
        entity_id=entity_id,
        observed_state=state,
        confidence=confidence,
    )


def test_history_tracks_transitions(observed_sim):
    world = observed_sim.world
    world.apply_observation(_obs(world, "p17", {"status": "packed"}, ts=2000.0))
    world.apply_observation(_obs(world, "p17", {"status": "shipped"}, ts=3000.0))
    hist = world.history("p17", attr="status")
    assert [h["new"] for h in hist] == ["packed", "shipped"]
    assert hist[0]["old"] == "intake"
    assert hist[0]["caused_by"]["kind"] == "observation"


def test_state_at_reconstructs_past(observed_sim):
    world = observed_sim.world
    world.apply_observation(_obs(world, "p17", {"status": "packed"}, ts=2000.0))
    past = world.state_at("p17", 1500.0)
    assert past["status"] == "intake"
    present = world.state_at("p17", 2500.0)
    assert present["status"] == "packed"


def test_what_changed_since(observed_sim):
    world = observed_sim.world
    world.apply_observation(_obs(world, "p17", {"status": "packed"}, ts=2000.0))
    changed = world.what_changed(since=1500.0)
    assert all(e["ts"] > 1500.0 for e in changed)
    assert any(e["type"] == "state_changed" for e in changed)
    assert world.what_changed(since=1_800_000_000.0) == []


def test_evidence_for_belief(observed_sim):
    world = observed_sim.world
    ev = world.evidence_for("p17", "zone_id")
    assert ev["value"] == "storage-a"
    assert ev["evidence"]["source"] == "sim-camera-1"
    assert ev["evidence"]["observation_id"] is not None
    # The observation itself is retrievable: full evidential chain.
    obs_ids = [o.id for o in world.observations]
    assert ev["evidence"]["observation_id"] in obs_ids


def test_evidence_without_observation(observed_sim):
    world = observed_sim.world
    # 'weight_kg' was in the initial file but never observed (sim reports
    # full state, so instead check a fabricated attribute path).
    ev = world.evidence_for("p17", "nonexistent_attr")
    assert ev["value"] is None
    assert ev["evidence"] is None
