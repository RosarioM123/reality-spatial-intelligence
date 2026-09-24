"""Constraint checks: the rules that gate action authorization.

A Constraint is data (see models.py); the actual check is a plain function
registered here under the constraint's `check` key, with signature
`check(action, world, constraint) -> (ok: bool, reason: str)`.

Keeping checks as small pure functions (rather than a rule language) is a
deliberate v0 choice: they are easy to test, easy to read, and new checks
are added by writing a function plus one registry line.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reality.core.models import Action, Constraint
    from reality.core.world import RealityWorld

Check = Callable[["Action", "RealityWorld", "Constraint"], tuple[bool, str]]


def check_entity_must_exist(
    action: Action, world: RealityWorld, constraint: Constraint
) -> tuple[bool, str]:
    if action.target not in world.spatial.entities:
        return False, f"target entity {action.target!r} does not exist"
    return True, ""


def check_target_zone_must_exist(
    action: Action, world: RealityWorld, constraint: Constraint
) -> tuple[bool, str]:
    to_zone = action.parameters.get("to_zone")
    if to_zone is None:
        return False, "move action is missing required parameter 'to_zone'"
    if to_zone not in world.spatial.zones:
        return False, f"destination zone {to_zone!r} does not exist"
    return True, ""


def check_zone_boundary_forbidden(
    action: Action, world: RealityWorld, constraint: Constraint
) -> tuple[bool, str]:
    """Entity kinds that may never enter certain zones (safety boundary)."""
    to_zone = action.parameters.get("to_zone")
    entity = world.spatial.entities.get(action.target)
    kinds = constraint.parameters.get("entity_kinds", [])
    forbidden = constraint.parameters.get("forbidden_zones", [])
    if entity is not None and entity.kind in kinds and to_zone in forbidden:
        return (
            False,
            (
                f"{entity.kind} {entity.id!r} may not enter zone {to_zone!r} "
                f"(boundary constraint {constraint.id!r})"
            ),
        )
    return True, ""


def check_resource_must_be_available(
    action: Action, world: RealityWorld, constraint: Constraint
) -> tuple[bool, str]:
    entity = world.spatial.entities.get(action.target)
    if entity is None:
        return False, f"target entity {action.target!r} does not exist"
    availability = entity.state.get("availability", "available")
    if availability != "available":
        return (
            False,
            (
                f"{entity.id!r} is {availability!r}, not available "
                f"(reserved_by={entity.state.get('reserved_by')!r})"
            ),
        )
    return True, ""


def check_approval_required(
    action: Action, world: RealityWorld, constraint: Constraint
) -> tuple[bool, str]:
    """Human approval gate. Unlike hard rejections, a missing approval leaves
    the action in 'proposed' so it can be approved and authorized later."""
    if not action.authorization or not action.authorization.get("approved_by"):
        return (
            False,
            (
                f"action type {action.type!r} requires human approval "
                f"(constraint {constraint.id!r})"
            ),
        )
    return True, ""


CHECKS: dict[str, Check] = {
    "entity_must_exist": check_entity_must_exist,
    "target_zone_must_exist": check_target_zone_must_exist,
    "zone_boundary_forbidden": check_zone_boundary_forbidden,
    "resource_must_be_available": check_resource_must_be_available,
    "approval_required": check_approval_required,
}


def evaluate(action: Action, world: RealityWorld) -> list[tuple[Constraint, bool, str]]:
    """Run every constraint that applies to the action's type.

    Returns (constraint, ok, reason) triples. Unknown check keys fail closed:
    an unresolvable constraint blocks the action.
    """
    results = []
    for constraint in world.constraints:
        if action.type not in constraint.applies_to:
            continue
        check = CHECKS.get(constraint.check)
        if check is None:
            results.append((constraint, False, f"unknown check {constraint.check!r}"))
            continue
        ok, reason = check(action, world, constraint)
        results.append((constraint, ok, reason))
    return results
