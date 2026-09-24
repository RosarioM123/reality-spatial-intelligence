"""The REALITY world state engine.

RealityWorld is the canonical, in-memory representation of the environment
an AI acts upon. It layers the action/state model on top of the spatial
substrate (SpatialWorld):

  spatial:      zones, entity geometry, adjacency          (where)
  state:        per-entity attribute values + provenance  (what is true, and why)
  relationships: typed links between entities             (how things relate)
  observations: evidence, each with source/confidence/ts  (what was seen)
  events:       append-only log of everything that happened (what changed, why)
  actions:      action records with lifecycle status      (what was attempted)
  constraints:  rules limiting actions                   (what is allowed)

Epistemic rule (the heart of the thesis): the world's BELIEVED state changes
ONLY via observations. Actions change ground truth through an executor; the
world learns about it when an observation arrives. This is what lets the
verification layer distinguish "the executor reported success" from "I
independently observed the change".
"""

from __future__ import annotations

import copy
import time
from collections.abc import Callable
from typing import Any

from reality.core import geometry
from reality.core.models import (
    Action,
    Constraint,
    Entity,
    Event,
    Observation,
    Point,
    Provenance,
    Relationship,
    SpatialWorld,
)

WORLD_VERSION = "reality/v0"


class WorldValidationError(ValueError):
    """Raised when a world description fails validation."""


class RealityWorld:
    """Canonical state of the environment. In-memory; JSON-serializable."""

    def __init__(
        self,
        spatial: SpatialWorld | None = None,
        now: Callable[[], float] | None = None,
    ):
        self.spatial = spatial or SpatialWorld()
        self.relationships: list[Relationship] = []
        self.observations: list[Observation] = []
        self.events: list[Event] = []
        self.actions: dict[str, Action] = {}
        self.constraints: list[Constraint] = []
        self.capabilities: dict[str, list[str]] = {}
        self._now = now or time.time
        self._id_counters: dict[str, int] = {}
        # Baseline snapshot for temporal reconstruction (state_at).
        self._baseline: dict[str, dict[str, Any]] = {}

    # -- ids and time ------------------------------------------------------
    def now(self) -> float:
        return self._now()

    def new_id(self, prefix: str) -> str:
        n = self._id_counters.get(prefix, 0) + 1
        self._id_counters[prefix] = n
        return f"{prefix}-{n}"

    # -- events ------------------------------------------------------------
    def _log(
        self,
        type: str,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
        caused_by: dict[str, str] | None = None,
        actor: str | None = None,
        ts: float | None = None,
    ) -> Event:
        event = Event(
            id=self.new_id("evt"),
            ts=ts if ts is not None else self.now(),
            type=type,
            entity_id=entity_id,
            details=details or {},
            caused_by=caused_by,
            actor=actor,
        )
        self.events.append(event)
        return event

    # -- attribute access --------------------------------------------------
    def get_attribute(self, entity_id: str, attr: str) -> Any:
        """Believed value of an attribute (location attrs included)."""
        entity = self.spatial.entities[entity_id]
        if attr == "zone_id":
            return entity.zone_id
        if attr == "position":
            return entity.position.to_list()
        return entity.state.get(attr)

    def get_provenance(self, entity_id: str, attr: str) -> Provenance | None:
        return self.spatial.entities[entity_id].state_provenance.get(attr)

    # -- observations: the only writer of believed state -------------------
    def apply_observation(self, obs: Observation) -> list[Event]:
        """Merge an observation into believed state.

        Returns the events produced (always at least observation_recorded).
        State changes generate state_changed events. A low-confidence
        report that contradicts a high-confidence belief logs
        observation_conflict and does NOT overwrite the belief; the
        contradictory reading stays in the observation record.
        """
        produced: list[Event] = []
        produced.append(
            self._log(
                "observation_recorded",
                entity_id=obs.entity_id,
                details={
                    "observation_id": obs.id,
                    "source": obs.source,
                    "confidence": obs.confidence,
                    "reported": obs.observed_state,
                },
                caused_by={"kind": "observation", "id": obs.id},
                ts=obs.ts,
            )
        )
        self.observations.append(obs)

        entity = self.spatial.entities.get(obs.entity_id)
        if entity is None:
            produced.append(
                self._log(
                    "observation_for_unknown_entity",
                    entity_id=obs.entity_id,
                    details={"observation_id": obs.id},
                    caused_by={"kind": "observation", "id": obs.id},
                    ts=obs.ts,
                )
            )
            return produced

        for attr, value in obs.observed_state.items():
            produced.extend(self._apply_attribute(entity, attr, value, obs))
        return produced

    def _apply_attribute(
        self, entity: Entity, attr: str, value: Any, obs: Observation
    ) -> list[Event]:
        produced: list[Event] = []
        old = self._read_attr(entity, attr)
        new = self._normalize_attr(attr, value)

        prev_prov = entity.state_provenance.get(attr)
        if (
            prev_prov is not None
            and old != new
            and obs.confidence + 0.3 < prev_prov.confidence
        ):
            # Weak new evidence contradicts strong existing belief:
            # log the conflict, keep the reading on record, but do NOT
            # let a low-confidence observation overwrite a
            # high-confidence belief. The conflict event is the signal
            # that something (sensor fault, spoofing, stale data) needs
            # attention.
            produced.append(
                self._log(
                    "observation_conflict",
                    entity_id=entity.id,
                    details={
                        "attribute": attr,
                        "believed": old,
                        "reported": new,
                        "believed_confidence": prev_prov.confidence,
                        "reported_confidence": obs.confidence,
                        "observation_id": obs.id,
                    },
                    caused_by={"kind": "observation", "id": obs.id},
                    ts=obs.ts,
                )
            )
            return produced

        if old != new:
            self._write_attr(entity, attr, new)
            produced.append(
                self._log(
                    "state_changed",
                    entity_id=entity.id,
                    details={
                        "attribute": attr,
                        "old": old,
                        "new": new,
                        "observation_id": obs.id,
                    },
                    caused_by={"kind": "observation", "id": obs.id},
                    ts=obs.ts,
                )
            )
        entity.state_provenance[attr] = Provenance(
            observed_at=obs.ts,
            source=obs.source,
            confidence=obs.confidence,
            observation_id=obs.id,
        )
        return produced

    @staticmethod
    def _read_attr(entity: Entity, attr: str) -> Any:
        if attr == "zone_id":
            return entity.zone_id
        if attr == "position":
            return entity.position.to_list()
        return entity.state.get(attr)

    @staticmethod
    def _normalize_attr(attr: str, value: Any) -> Any:
        if attr == "position" and isinstance(value, (list, tuple)):
            return Point.from_list(list(value)).to_list()
        return value

    @staticmethod
    def _write_attr(entity: Entity, attr: str, value: Any) -> None:
        if attr == "zone_id":
            entity.zone_id = value
        elif attr == "position":
            entity.position = Point.from_list(list(value))
        else:
            entity.state[attr] = value

    # -- temporal queries --------------------------------------------------
    def history(self, entity_id: str, attr: str | None = None) -> list[dict[str, Any]]:
        """Ordered state transitions for an entity (optionally one attribute)."""
        out = []
        for e in self.events:
            if e.type != "state_changed" or e.entity_id != entity_id:
                continue
            if attr is not None and e.details.get("attribute") != attr:
                continue
            out.append(
                {
                    "ts": e.ts,
                    "attribute": e.details.get("attribute"),
                    "old": e.details.get("old"),
                    "new": e.details.get("new"),
                    "caused_by": e.caused_by,
                    "observation_id": e.details.get("observation_id"),
                }
            )
        return out

    def state_at(self, entity_id: str, ts: float) -> dict[str, Any] | None:
        """Reconstruct believed attribute values as of time ts."""
        if entity_id not in self._baseline:
            return None
        state = copy.deepcopy(self._baseline[entity_id])
        for e in self.events:
            if e.type != "state_changed" or e.entity_id != entity_id:
                continue
            if e.ts > ts:
                break
            state[e.details["attribute"]] = e.details["new"]
        return state

    def what_changed(self, since: float) -> list[dict[str, Any]]:
        """All events after timestamp `since`, oldest first."""
        return [e.to_dict() for e in self.events if e.ts > since]

    def evidence_for(self, entity_id: str, attr: str) -> dict[str, Any] | None:
        """The evidential chain behind a current belief: value, provenance,
        and the observation that produced it."""
        entity = self.spatial.entities.get(entity_id)
        if entity is None:
            return None
        prov = entity.state_provenance.get(attr)
        if prov is None:
            return {
                "entity_id": entity_id,
                "attribute": attr,
                "value": self._read_attr(entity, attr),
                "evidence": None,
                "note": "no observation on record; value is the initial belief",
            }
        obs = next((o for o in self.observations if o.id == prov.observation_id), None)
        return {
            "entity_id": entity_id,
            "attribute": attr,
            "value": self._read_attr(entity, attr),
            "evidence": {
                "observation_id": prov.observation_id,
                "source": prov.source,
                "confidence": prov.confidence,
                "observed_at": prov.observed_at,
                "reported": obs.observed_state if obs else None,
            },
        }

    # -- relationships -----------------------------------------------------
    def related(
        self, entity_id: str, predicate: str | None = None
    ) -> list[Relationship]:
        return [
            r
            for r in self.relationships
            if r.subject_id == entity_id
            and (predicate is None or r.predicate == predicate)
        ]

    # -- validation --------------------------------------------------------
    def validate(self) -> list[str]:
        problems: list[str] = []
        zone_ids = set(self.spatial.zones)
        for rel in self.relationships:
            if rel.subject_id not in self.spatial.entities:
                problems.append(
                    f"relationship {rel.predicate!r} references unknown "
                    f"subject {rel.subject_id!r}"
                )
            if (
                rel.object_id not in self.spatial.entities
                and rel.object_id not in zone_ids
            ):
                problems.append(
                    f"relationship {rel.predicate!r} references unknown "
                    f"object {rel.object_id!r}"
                )
        for c in self.constraints:
            if not c.check:
                problems.append(f"constraint {c.id!r} has no check registered")
        for kind, actions in self.capabilities.items():
            for a in actions:
                if not isinstance(a, str):
                    problems.append(
                        f"capability for kind {kind!r} is not a string: {a!r}"
                    )
        return problems

    def snapshot_baseline(self) -> None:
        """Record current attribute values as the temporal baseline."""
        self._baseline = {}
        for eid, entity in self.spatial.entities.items():
            snap: dict[str, Any] = {
                "zone_id": entity.zone_id,
                "position": entity.position.to_list(),
            }
            snap.update(copy.deepcopy(entity.state))
            self._baseline[eid] = snap

    # -- serialization -----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "version": WORLD_VERSION,
            "spatial": self.spatial.to_dict(),
            "relationships": [r.to_dict() for r in self.relationships],
            "observations": [o.to_dict() for o in self.observations],
            "events": [e.to_dict() for e in self.events],
            "actions": [a.to_dict() for a in self.actions.values()],
            "constraints": [c.to_dict() for c in self.constraints],
            "capabilities": self.capabilities,
            "id_counters": self._id_counters,
            "baseline": self._baseline,
        }

    @staticmethod
    def from_dict(
        data: dict[str, Any], now: Callable[[], float] | None = None
    ) -> RealityWorld:
        spatial_data = data.get("spatial", data)
        world = RealityWorld(spatial=SpatialWorld.from_dict(spatial_data), now=now)
        world.relationships = [
            Relationship.from_dict(r) for r in data.get("relationships", [])
        ]
        world.observations = [
            Observation.from_dict(o) for o in data.get("observations", [])
        ]
        world.events = [Event.from_dict(e) for e in data.get("events", [])]
        for a in data.get("actions", []):
            action = Action.from_dict(a)
            world.actions[action.id] = action
        world.constraints = [
            Constraint.from_dict(c) for c in data.get("constraints", [])
        ]
        world.capabilities = {
            k: list(v) for k, v in data.get("capabilities", {}).items()
        }
        world._id_counters = {k: int(v) for k, v in data.get("id_counters", {}).items()}
        world._baseline = copy.deepcopy(data.get("baseline", {}))
        if not world._baseline:
            world.snapshot_baseline()
        # Rebuild the spatial index lazily via the pipeline when needed.
        return world

    def spatial_pipeline(self):
        """The spatial query substrate over current believed geometry."""
        from reality.core.pipeline import SpatialPipeline

        return SpatialPipeline(self.spatial)

    def zone_centroid(self, zone_id: str) -> Point:
        return geometry.centroid(self.spatial.zones[zone_id].polygon)
