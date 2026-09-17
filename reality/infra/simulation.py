"""Deterministic simulation: the first ObservationSource/ActionExecutor pair.

The simulation keeps TWO things strictly separate:

  ground_truth  -- what is ACTUALLY true in the simulated world
                  (dict: entity_id -> {"zone_id", "position", "state"})
  world         -- what the AI BELIEVES (a RealityWorld)

The executor mutates ground truth. The observation source reads ground
truth and emits observations. The world only learns via observations.
That separation is what makes discrepancy detection (executor says
"success", observation says otherwise) possible and honest.

Fault injection (for the failure demo and tests):
  faults = {"<action-id>": "report_success_without_effect"}
           {"<action-id>": "wrong_effect", ...}  -- applies a different zone
Without faults the simulator is faithful: what the executor reports is
what the next observation shows.

Everything is deterministic: the clock only moves when tick() is called,
ids are counters, and there is no randomness.
"""

from __future__ import annotations

import copy
from typing import Any

from reality.core import geometry
from reality.core.actions import ActionEngine
from reality.core.models import Action, Observation
from reality.core.pipeline import validate_world
from reality.core.world import RealityWorld, WorldValidationError
from reality.infra.adapters import ActionExecutor, ObservationSource

# Fixed start time so runs are reproducible (2026-01-01 00:00:00 UTC).
SIM_EPOCH = 1_767_225_600.0


class SimClock:
    def __init__(self, start: float = SIM_EPOCH):
        self.t = start

    def now(self) -> float:
        return self.t

    def tick(self, dt: float = 1.0) -> float:
        self.t += dt
        return self.t


class SimActionExecutor(ActionExecutor):
    """Applies action effects to simulated ground truth."""

    def __init__(self, sim: "Simulation"):
        self.sim = sim

    def execute(self, action: Action) -> dict[str, Any]:
        truth = self.sim.ground_truth.get(action.target)
        if truth is None:
            return {"success": False,
                    "message": f"no such entity {action.target!r}"}

        fault = (self.sim.faults or {}).get(action.id)

        if action.type == "move_entity":
            to_zone = action.parameters.get("to_zone")
            if to_zone not in self.sim.world.spatial.zones:
                return {"success": False,
                        "message": f"unknown zone {to_zone!r}"}
            if fault == "report_success_without_effect":
                return {"success": True,
                        "message": f"moved {action.target} to {to_zone} "
                                   f"(fault: effect suppressed)"}
            zone = to_zone
            if fault == "wrong_effect":
                zone = self.sim.faults[action.id + ":to_zone"]
            centroid = geometry.centroid(
                self.sim.world.spatial.zones[zone].polygon
            )
            truth["zone_id"] = zone
            truth["position"] = centroid.to_list()
            return {"success": True,
                    "message": f"moved {action.target} to {zone}"}

        if action.type == "reserve_resource":
            truth["state"]["availability"] = "reserved"
            truth["state"]["reserved_by"] = action.parameters.get("for_whom")
            return {"success": True,
                    "message": f"reserved {action.target}"}

        if action.type == "change_status":
            truth["state"]["status"] = action.parameters.get("status")
            return {"success": True,
                    "message": f"status of {action.target} -> "
                               f"{action.parameters.get('status')!r}"}

        if action.type == "assign_entity":
            truth["state"]["assignee"] = action.parameters.get("assignee")
            return {"success": True,
                    "message": f"assigned {action.target}"}

        if action.type == "notify":
            return {"success": True,
                    "message": f"notified: {action.parameters.get('message')}"}

        return {"success": False,
                "message": f"sim cannot execute {action.type!r}"}


class SimObservationSource(ObservationSource):
    """Reads ground truth and emits observations, like a camera network."""

    def __init__(
        self,
        sim: "Simulation",
        source_id: str = "sim-camera-1",
        confidence: float = 0.95,
        spoof: dict[str, dict[str, Any]] | None = None,
    ):
        self.sim = sim
        self.source_id = source_id
        self.confidence = confidence
        # spoof: entity_id -> {attr: false_value}; reports lies (for tests).
        self.spoof = spoof or {}

    def poll(self, world: RealityWorld) -> list[Observation]:
        observations = []
        for entity_id, truth in self.sim.ground_truth.items():
            reported: dict[str, Any] = {
                "zone_id": truth["zone_id"],
                "position": list(truth["position"]),
            }
            reported.update(copy.deepcopy(truth["state"]))
            for attr, false_value in self.spoof.get(entity_id, {}).items():
                reported[attr] = false_value
            observations.append(
                Observation(
                    id=world.new_id("obs"),
                    ts=self.sim.clock.now(),
                    source=self.source_id,
                    entity_id=entity_id,
                    observed_state=reported,
                    confidence=self.confidence,
                    context=f"simulated observation at t={self.sim.clock.now()}",
                )
            )
        return observations


class Simulation:
    """A deterministic simulated environment: clock + ground truth +
    executor + observation source + the believed world + the action engine."""

    def __init__(
        self,
        world_data: dict[str, Any],
        faults: dict[str, Any] | None = None,
        start_ts: float = SIM_EPOCH,
    ):
        self.clock = SimClock(start_ts)
        self.world = RealityWorld.from_dict(world_data, now=self.clock.now)
        problems = validate_world(self.world.spatial) + self.world.validate()
        if problems:
            raise WorldValidationError("; ".join(problems))
        self.faults = faults or {}
        # Ground truth starts identical to the world's initial beliefs.
        self.ground_truth: dict[str, dict[str, Any]] = {}
        for eid, entity in self.world.spatial.entities.items():
            self.ground_truth[eid] = {
                "zone_id": entity.zone_id,
                "position": entity.position.to_list(),
                "state": copy.deepcopy(entity.state),
            }
        self.executor = SimActionExecutor(self)
        self.source = SimObservationSource(self)
        self.engine = ActionEngine(
            self.world, self.executor, observer=self._observe
        )

    def _observe(self) -> list[Observation]:
        self.clock.tick()
        return self.source.poll(self.world)

    def observe(self) -> list[Observation]:
        """One observation round: poll sources, merge into believed world."""
        observations = self._observe()
        for obs in observations:
            self.world.apply_observation(obs)
        return observations

    def act(
        self,
        type: str,
        actor: str,
        target: str,
        parameters: dict[str, Any] | None = None,
        approved_by: str | None = None,
        provenance: str = "simulation",
    ) -> Action:
        """Full action loop: propose -> authorize -> execute ->
        observe -> verify."""
        self.clock.tick()
        return self.engine.run(
            type, actor, target, parameters,
            approved_by=approved_by, provenance=provenance,
        )

    def add_fault(self, action_id: str, fault: Any, **kwargs: Any) -> None:
        self.faults[action_id] = fault
        for k, v in kwargs.items():
            self.faults[f"{action_id}:{k}"] = v

    def to_dict(self) -> dict[str, Any]:
        d = self.world.to_dict()
        d["ground_truth"] = copy.deepcopy(self.ground_truth)
        d["sim_time"] = self.clock.now()
        return d
