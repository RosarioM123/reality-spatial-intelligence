"""The action engine: propose -> authorize -> execute -> observe -> verify.

Actions are the AI's hands in the world. The engine enforces the lifecycle:

  proposed --(authorize: constraints pass)--> authorized
  proposed --(authorize: hard constraint fails)--> rejected
  proposed --(authorize: only approval missing)--> proposed (awaiting approval)
  authorized --(execute: executor runs)--> executing --> executed | failed
  executed --(observation arrives)--> observed
  observed --(verify)--> verified | partially_verified | failed

Every transition is recorded as an event with provenance. The engine never
mutates believed world state itself: execution goes through an ActionExecutor
(which changes ground truth), and belief changes only when observations are
applied to the world.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from reality.core import constraints as constraint_checks
from reality.core.models import (
    ACTION_AUTHORIZED,
    ACTION_EXECUTED,
    ACTION_EXECUTING,
    ACTION_FAILED,
    ACTION_OBSERVED,
    ACTION_PARTIALLY_VERIFIED,
    ACTION_PROPOSED,
    ACTION_REJECTED,
    ACTION_VERIFIED,
    Action,
    Observation,
)
from reality.core.verification import (
    PARTIALLY_VERIFIED,
    VERIFIED,
    verify_action,
)
from reality.core.world import RealityWorld

# The v0 action set: small on purpose. Each entry documents its parameters;
# expected_effect() below defines what "success" observably means.
ACTION_SCHEMAS: dict[str, dict[str, Any]] = {
    "move_entity": {
        "params": ["to_zone"],
        "description": "Move an entity to another zone.",
    },
    "reserve_resource": {
        "params": ["for_whom"],
        "description": "Reserve an available resource for someone.",
    },
    "change_status": {
        "params": ["status"],
        "description": "Set an entity's status attribute.",
    },
    "assign_entity": {
        "params": ["assignee"],
        "description": "Assign an entity to a person or team.",
    },
    "notify": {
        "params": ["message"],
        "description": "Send a notification. No observable world effect.",
    },
}


def expected_effect_for(action: Action) -> dict[str, dict[str, Any]]:
    """What observable state change this action intends, if any."""
    p = action.parameters
    if action.type == "move_entity":
        return {action.target: {"zone_id": p.get("to_zone")}}
    if action.type == "reserve_resource":
        return {
            action.target: {
                "availability": "reserved",
                "reserved_by": p.get("for_whom"),
            }
        }
    if action.type == "change_status":
        return {action.target: {"status": p.get("status")}}
    if action.type == "assign_entity":
        return {action.target: {"assignee": p.get("assignee")}}
    return {}  # notify and unknown types: no observable effect


class ActionEngine:
    """Drives the action lifecycle against a RealityWorld."""

    def __init__(
        self,
        world: RealityWorld,
        executor: Any = None,  # ActionExecutor (duck-typed to avoid import cycle)
        observer: Callable[[], list[Observation]] | None = None,
    ):
        self.world = world
        self.executor = executor
        self.observer = observer

    # -- lifecycle ---------------------------------------------------------
    def propose(
        self,
        type: str,
        actor: str,
        target: str,
        parameters: dict[str, Any] | None = None,
        provenance: str = "",
    ) -> Action:
        if type not in ACTION_SCHEMAS:
            raise ValueError(f"unknown action type {type!r}")
        entity = self.world.spatial.entities.get(target)
        offered = self.world.capabilities.get(entity.kind, []) if entity else []
        if entity is not None and self.world.capabilities and type not in offered:
            raise ValueError(
                f"action {type!r} is not offered for kind {entity.kind!r} "
                f"(capabilities: {offered})"
            )
        action = Action(
            id=self.world.new_id("act"),
            type=type,
            actor=actor,
            target=target,
            parameters=parameters or {},
            status=ACTION_PROPOSED,
            created_at=self.world.now(),
            provenance=provenance,
        )
        action.expected_effect = expected_effect_for(action)
        self.world.actions[action.id] = action
        self.world._log(
            "action_proposed",
            entity_id=target,
            details={
                "action_id": action.id,
                "type": type,
                "parameters": action.parameters,
                "expected_effect": action.expected_effect,
            },
            caused_by={"kind": "action", "id": action.id},
            actor=actor,
        )
        return action

    def authorize(
        self, action: Action, approved_by: str | None = None
    ) -> tuple[bool, str]:
        """Check constraints. Returns (ok, message)."""
        if action.status not in (ACTION_PROPOSED, ACTION_REJECTED):
            return False, f"cannot authorize action in status {action.status!r}"
        if approved_by:
            action.authorization = {
                "approved_by": approved_by,
                "approved_at": self.world.now(),
            }
        results = constraint_checks.evaluate(action, self.world)
        failures = [(c, r) for c, ok, r in results if not ok]
        if failures:
            hard = [c for c, _ in failures if c.kind != "approval"]
            reasons = "; ".join(r for _, r in failures)
            if hard:
                action.status = ACTION_REJECTED
                action.rejection_reason = reasons
                self.world._log(
                    "action_rejected",
                    entity_id=action.target,
                    details={"action_id": action.id, "reasons": reasons},
                    caused_by={"kind": "action", "id": action.id},
                    actor=action.actor,
                )
                return False, f"rejected: {reasons}"
            # Only approval missing: stay proposed, await approval.
            return False, f"awaiting approval: {reasons}"
        action.status = ACTION_AUTHORIZED
        action.authorized_at = self.world.now()
        self.world._log(
            "action_authorized",
            entity_id=action.target,
            details={
                "action_id": action.id,
                "approved_by": approved_by,
            },
            caused_by={"kind": "action", "id": action.id},
            actor=action.actor,
        )
        return True, "authorized"

    def execute(self, action: Action) -> tuple[bool, str]:
        if action.status != ACTION_AUTHORIZED:
            return False, f"cannot execute action in status {action.status!r}"
        action.status = ACTION_EXECUTING
        try:
            report = self.executor.execute(action)
        except Exception as exc:  # noqa: BLE001 -- executors must not take the engine down
            report = {"success": False, "message": f"executor error: {exc}"}
        action.executor_report = dict(report)
        action.executed_at = self.world.now()
        if report.get("success"):
            action.status = ACTION_EXECUTED
            self.world._log(
                "action_executed",
                entity_id=action.target,
                details={
                    "action_id": action.id,
                    "report": action.executor_report,
                },
                caused_by={"kind": "action", "id": action.id},
                actor=action.actor,
            )
            return True, str(report.get("message", "executed"))
        action.status = ACTION_FAILED
        self.world._log(
            "action_failed",
            entity_id=action.target,
            details={
                "action_id": action.id,
                "report": action.executor_report,
            },
            caused_by={"kind": "action", "id": action.id},
            actor=action.actor,
        )
        return False, str(report.get("message", "execution failed"))

    def ingest_observations(self, action: Action) -> list[Observation]:
        """Poll the observer, apply observations, mark the action observed."""
        observations: list[Observation] = []
        if self.observer is not None:
            observations = self.observer()
            for obs in observations:
                self.world.apply_observation(obs)
        if action.status == ACTION_EXECUTED:
            action.status = ACTION_OBSERVED
            action.observed_at = self.world.now()
            self.world._log(
                "action_observed",
                entity_id=action.target,
                details={
                    "action_id": action.id,
                    "observations_applied": [o.id for o in observations],
                },
                caused_by={"kind": "action", "id": action.id},
                actor=action.actor,
            )
        return observations

    def verify(self, action: Action):
        """Compare expected vs observed state; finalize the action."""
        if action.status not in (ACTION_OBSERVED, ACTION_EXECUTED):
            raise ValueError(f"cannot verify action in status {action.status!r}")
        result = verify_action(action, self.world, self.world.now())
        action.verification = result.to_dict()
        action.verified_at = self.world.now()
        # Record what actually happened, per attribute.
        actual: dict[str, dict[str, Any]] = {}
        for check in result.checked:
            actual.setdefault(check["entity_id"], {})[check["attribute"]] = check[
                "actual"
            ]
        action.actual_effect = actual
        if result.status == VERIFIED:
            action.status = ACTION_VERIFIED
        elif result.status == PARTIALLY_VERIFIED:
            action.status = ACTION_PARTIALLY_VERIFIED
        else:
            action.status = ACTION_FAILED
        self.world._log(
            "action_verified",
            entity_id=action.target,
            details={
                "action_id": action.id,
                "verification": result.to_dict(),
            },
            caused_by={"kind": "action", "id": action.id},
            actor=action.actor,
        )
        return result

    # -- convenience: the full loop ----------------------------------------
    def run(
        self,
        type: str,
        actor: str,
        target: str,
        parameters: dict[str, Any] | None = None,
        approved_by: str | None = None,
        provenance: str = "",
    ) -> Action:
        """propose -> authorize -> execute -> observe -> verify, stopping at
        the first step that does not proceed. Returns the action record."""
        action = self.propose(type, actor, target, parameters, provenance)
        ok, _ = self.authorize(action, approved_by=approved_by)
        if not ok:
            return action
        ok, _ = self.execute(action)
        if not ok:
            return action
        self.ingest_observations(action)
        self.verify(action)
        return action

    # -- introspection -----------------------------------------------------
    def available_actions(
        self, entity_id: str | None = None, zone_id: str | None = None
    ) -> list[dict[str, Any]]:
        """What actions could be taken, annotated with constraint notes."""
        out: list[dict[str, Any]] = []
        entities = self.world.spatial.entities
        candidates = (
            [entities[entity_id]]
            if entity_id
            else (
                [e for e in entities.values() if e.zone_id == zone_id]
                if zone_id
                else list(entities.values())
            )
        )
        for entity in candidates:
            for action_type in self.world.capabilities.get(entity.kind, []):
                schema = ACTION_SCHEMAS.get(action_type, {})
                notes = []
                for constraint in self.world.constraints:
                    if action_type in constraint.applies_to:
                        notes.append(f"{constraint.kind}: {constraint.description}")
                out.append(
                    {
                        "entity_id": entity.id,
                        "entity_name": entity.name,
                        "kind": entity.kind,
                        "action": action_type,
                        "params": schema.get("params", []),
                        "description": schema.get("description", ""),
                        "constraints": notes,
                    }
                )
        return out
