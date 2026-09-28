"""Direct unit tests for the constraint checks (reality/core/constraints.py).

The checks gate action authorization; each is a small pure function of
(action, world, constraint), so they are tested in isolation here rather
than only through the engine.
"""

import pytest

from reality.core import constraints
from reality.core.models import Action, Constraint


_MISSING = object()


def _action(target="p17", type="move_entity", parameters=_MISSING, authorization=None):
    return Action(
        id="a-test",
        type=type,
        actor="test-agent",
        target=target,
        parameters={"to_zone": "storage-b"} if parameters is _MISSING else parameters,
        authorization=authorization,
    )


def _constraint(check, applies_to=None, parameters=None):
    return Constraint(
        id="c-test",
        name="test constraint",
        kind="safety",
        applies_to=applies_to or ["move_entity"],
        check=check,
        parameters=parameters or {},
    )


def test_entity_must_exist_rejects_unknown_target(sim):
    c = _constraint("entity_must_exist")
    ok, reason = constraints.check_entity_must_exist(
        _action(target="nope"), sim.world, c
    )
    assert not ok
    assert "nope" in reason


def test_entity_must_exist_accepts_known_target(sim):
    ok, _ = constraints.check_entity_must_exist(_action(), sim.world, _constraint("entity_must_exist"))
    assert ok


def test_target_zone_must_exist_rejects_missing_parameter(sim):
    ok, reason = constraints.check_target_zone_must_exist(
        _action(parameters={}), sim.world, _constraint("target_zone_must_exist")
    )
    assert not ok
    assert "to_zone" in reason


def test_target_zone_must_exist_rejects_unknown_zone(sim):
    ok, reason = constraints.check_target_zone_must_exist(
        _action(parameters={"to_zone": "moon"}),
        sim.world,
        _constraint("target_zone_must_exist"),
    )
    assert not ok
    assert "moon" in reason


def test_target_zone_must_exist_accepts_known_zone(sim):
    ok, _ = constraints.check_target_zone_must_exist(
        _action(), sim.world, _constraint("target_zone_must_exist")
    )
    assert ok


def test_zone_boundary_forbidden_blocks_listed_kind(sim):
    c = _constraint(
        "zone_boundary_forbidden",
        parameters={"entity_kinds": ["package"], "forbidden_zones": ["office"]},
    )
    ok, reason = constraints.check_zone_boundary_forbidden(
        _action(parameters={"to_zone": "office"}), sim.world, c
    )
    assert not ok
    assert "office" in reason


def test_zone_boundary_forbidden_allows_other_kinds(sim):
    c = _constraint(
        "zone_boundary_forbidden",
        parameters={"entity_kinds": ["equipment"], "forbidden_zones": ["office"]},
    )
    ok, _ = constraints.check_zone_boundary_forbidden(
        _action(parameters={"to_zone": "office"}), sim.world, c
    )
    assert ok


def test_zone_boundary_forbidden_allows_unlisted_zone(sim):
    c = _constraint(
        "zone_boundary_forbidden",
        parameters={"entity_kinds": ["package"], "forbidden_zones": ["office"]},
    )
    ok, _ = constraints.check_zone_boundary_forbidden(_action(), sim.world, c)
    assert ok


def test_resource_must_be_available_rejects_reserved(sim):
    ok, reason = constraints.check_resource_must_be_available(
        _action(target="p18"), sim.world, _constraint("resource_must_be_available")
    )
    assert not ok
    assert "reserved" in reason
    assert "team-ops" in reason


def test_resource_must_be_available_accepts_available(sim):
    ok, _ = constraints.check_resource_must_be_available(
        _action(), sim.world, _constraint("resource_must_be_available")
    )
    assert ok


def test_resource_must_be_available_rejects_missing_entity(sim):
    ok, _ = constraints.check_resource_must_be_available(
        _action(target="nope"), sim.world, _constraint("resource_must_be_available")
    )
    assert not ok


def test_approval_required_blocks_unapproved(sim):
    ok, reason = constraints.check_approval_required(
        _action(), sim.world, _constraint("approval_required")
    )
    assert not ok
    assert "approval" in reason


def test_approval_required_accepts_approved(sim):
    ok, _ = constraints.check_approval_required(
        _action(authorization={"approved_by": "rosario", "approved_at": 1.0}),
        sim.world,
        _constraint("approval_required"),
    )
    assert ok


def test_evaluate_runs_only_matching_constraints(sim):
    sim.world.constraints = [
        _constraint("entity_must_exist", applies_to=["move_entity"]),
        _constraint("entity_must_exist", applies_to=["reserve_resource"]),
    ]
    results = constraints.evaluate(_action(), sim.world)
    assert len(results) == 1
    assert results[0][1] is True


def test_evaluate_fails_closed_on_unknown_check(sim):
    sim.world.constraints = [_constraint("no_such_check")]
    results = constraints.evaluate(_action(), sim.world)
    assert len(results) == 1
    constraint, ok, reason = results[0]
    assert not ok
    assert "unknown check" in reason


def test_registry_covers_all_checks():
    assert set(constraints.CHECKS) == {
        "entity_must_exist",
        "target_zone_must_exist",
        "zone_boundary_forbidden",
        "resource_must_be_available",
        "approval_required",
    }
