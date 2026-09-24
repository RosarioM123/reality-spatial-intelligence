"""Tests for the action lifecycle:
proposed -> authorized -> executed -> observed -> verified."""

import pytest


def test_full_lifecycle_success(observed_sim):
    sim = observed_sim
    action = sim.act(
        "move_entity",
        "tester",
        "p17",
        {"to_zone": "storage-b"},
        approved_by="rosario",
        provenance="test",
    )
    assert action.status == "verified"
    assert action.authorization["approved_by"] == "rosario"
    assert action.executor_report["success"] is True
    assert action.verification["status"] == "verified"
    assert action.created_at <= action.authorized_at <= action.executed_at
    assert action.observed_at <= action.verified_at
    # Every transition is an event.
    types = [
        e.type
        for e in sim.world.events
        if e.caused_by and e.caused_by.get("id") == action.id
    ]
    for expected in (
        "action_proposed",
        "action_authorized",
        "action_executed",
        "action_observed",
        "action_verified",
    ):
        assert expected in types


def test_move_requires_approval_first(observed_sim):
    sim = observed_sim
    engine = sim.engine
    action = engine.propose("move_entity", "tester", "p17", {"to_zone": "storage-b"})
    ok, msg = engine.authorize(action)
    assert ok is False
    assert "approval" in msg
    # Not rejected: still proposed, awaiting approval.
    assert action.status == "proposed"
    ok, _ = engine.authorize(action, approved_by="rosario")
    assert ok is True
    assert action.status == "authorized"


def test_hard_constraint_rejects(observed_sim):
    sim = observed_sim
    # Packages may not enter the office (boundary constraint).
    action = sim.engine.run(
        "move_entity", "tester", "p17", {"to_zone": "office"}, approved_by="rosario"
    )
    assert action.status == "rejected"


def test_unknown_zone_rejects(observed_sim):
    sim = observed_sim
    action = sim.engine.run(
        "move_entity", "tester", "p17", {"to_zone": "atlantis"}, approved_by="rosario"
    )
    assert action.status == "rejected"


def test_capabilities_are_enforced(observed_sim):
    sim = observed_sim
    # assign_entity is not offered for kind "package" in warehouse.json.
    with pytest.raises(ValueError, match="not offered"):
        sim.engine.propose("assign_entity", "tester", "p17", {"assignee": "ana"})


def test_unknown_action_type_rejected(observed_sim):
    sim = observed_sim
    with pytest.raises(ValueError, match="unknown action type"):
        sim.engine.propose("teleport", "tester", "p17", {})


def test_reserve_unavailable_resource_rejected(observed_sim):
    sim = observed_sim
    first = sim.act("reserve_resource", "tester", "forklift-1", {"for_whom": "ana"})
    assert first.status == "verified"
    # Already reserved: the second request is rejected by the constraint.
    second = sim.engine.run(
        "reserve_resource", "tester", "forklift-1", {"for_whom": "rosario"}
    )
    assert second.status == "rejected"
    assert "not available" in (second.rejection_reason or "")


def test_reserve_available_resource(observed_sim):
    sim = observed_sim
    action = sim.act("reserve_resource", "tester", "forklift-1", {"for_whom": "ana"})
    assert action.status == "verified"
    assert sim.world.get_attribute("forklift-1", "availability") == "reserved"
    assert sim.world.get_attribute("forklift-1", "reserved_by") == "ana"


def test_change_status_and_assign(observed_sim):
    sim = observed_sim
    a1 = sim.act("change_status", "tester", "dock-door-1", {"status": "open"})
    assert a1.status == "verified"
    assert sim.world.get_attribute("dock-door-1", "status") == "open"
    a2 = sim.act("assign_entity", "tester", "forklift-1", {"assignee": "ana"})
    assert a2.status == "verified"
    assert sim.world.get_attribute("forklift-1", "assignee") == "ana"


def test_notify_has_no_observable_effect(observed_sim):
    sim = observed_sim
    action = sim.act("notify", "tester", "ana", {"message": "shift ends at 18:00"})
    assert action.status == "verified"
    assert action.verification["status"] == "verified"


def test_execute_requires_authorization(observed_sim):
    sim = observed_sim
    action = sim.engine.propose(
        "change_status", "tester", "dock-door-1", {"status": "open"}
    )
    ok, _ = sim.engine.execute(action)
    assert ok is False
    assert action.status == "proposed"
