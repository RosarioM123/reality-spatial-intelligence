"""Tests for constraint checks and the verification layer."""

from reality.core import constraints as checks
from reality.core.models import Action
from reality.core.verification import verify_action


def _action(world, type="move_entity", target="p17", params=None,
            approved_by=None):
    action = Action(id=world.new_id("act"), type=type, actor="tester",
                    target=target, parameters=params or {},
                    created_at=world.now())
    if approved_by:
        action.authorization = {"approved_by": approved_by,
                                "approved_at": world.now()}
    return action


def test_evaluate_runs_applicable_checks(observed_sim):
    world = observed_sim.world
    action = _action(world, params={"to_zone": "storage-b"})
    results = checks.evaluate(action, world)
    kinds = {c.kind for c, _, _ in results}
    assert "approval" in kinds  # c-move-approval applies to move_entity
    assert "safety" in kinds


def test_approval_check(observed_sim):
    world = observed_sim.world
    constraint = next(c for c in world.constraints
                      if c.check == "approval_required")
    action = _action(world, params={"to_zone": "storage-b"})
    ok, reason = checks.CHECKS["approval_required"](action, world, constraint)
    assert ok is False and "approval" in reason
    action2 = _action(world, params={"to_zone": "storage-b"},
                      approved_by="rosario")
    ok, _ = checks.CHECKS["approval_required"](action2, world, constraint)
    assert ok is True


def test_boundary_check(observed_sim):
    world = observed_sim.world
    constraint = next(c for c in world.constraints
                      if c.check == "zone_boundary_forbidden")
    action = _action(world, params={"to_zone": "office"})
    ok, reason = checks.CHECKS["zone_boundary_forbidden"](
        action, world, constraint)
    assert ok is False and "office" in reason
    action2 = _action(world, params={"to_zone": "packing"})
    ok, _ = checks.CHECKS["zone_boundary_forbidden"](
        action2, world, constraint)
    assert ok is True


def test_unknown_check_fails_closed(observed_sim):
    from reality.core.models import Constraint
    world = observed_sim.world
    world.constraints.append(Constraint(
        id="c-bogus", name="bogus", kind="safety",
        applies_to=["move_entity"], check="no_such_check"))
    action = _action(world, params={"to_zone": "storage-b"},
                     approved_by="rosario")
    results = checks.evaluate(action, world)
    bogus = [r for c, r, _ in [(c, ok, rs) for c, ok, rs in results]
             if c.id == "c-bogus"]
    assert bogus and bogus[0] is False


def test_verify_verified(observed_sim):
    sim = observed_sim
    action = sim.act("move_entity", "tester", "p17", {"to_zone": "packing"},
                     approved_by="rosario")
    assert action.verification["status"] == "verified"
    assert action.verification["discrepancies"] == []


def test_verify_failed_on_contradiction(observed_sim):
    """Executor claims success; observation disagrees -> failed."""
    sim = observed_sim
    engine = sim.engine
    action = engine.propose("move_entity", "tester", "p17",
                            {"to_zone": "packing"}, provenance="test")
    sim.add_fault(action.id, "report_success_without_effect")
    engine.authorize(action, approved_by="rosario")
    ok, _ = engine.execute(action)
    assert ok is True  # the executor LIES successfully
    engine.ingest_observations(action)
    result = engine.verify(action)
    assert result.status == "failed"
    assert action.status == "failed"
    assert len(result.discrepancies) == 1
    assert "packing" in result.discrepancies[0]
    assert "storage-a" in result.discrepancies[0]


def test_verify_unknown_without_observation(sim):
    """Executed but never observed -> unknown, not verified."""
    engine = sim.engine  # no observation round run
    action = engine.propose("move_entity", "tester", "p17",
                            {"to_zone": "packing"})
    engine.authorize(action, approved_by="rosario")
    engine.execute(action)
    result = engine.verify(action)
    assert result.status == "unknown"


def test_verify_partially_verified(observed_sim):
    sim = observed_sim
    world = sim.world
    action = _action(sim.world, type="reserve_resource", target="forklift-1",
                     params={"for_whom": "ana"})
    # Fake an expected effect where one attribute matches and one does not.
    action.expected_effect = {
        "forklift-1": {"availability": "available", "status": "exploded"}
    }
    result = verify_action(action, world, world.now())
    assert result.status == "partially_verified"
    assert len(result.discrepancies) == 1
