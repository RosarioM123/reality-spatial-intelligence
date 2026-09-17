"""Core domain models for the spatial pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Point:
    """A 3D point. Zones use x/y; z is carried for future 3D use."""

    x: float
    y: float
    z: float = 0.0

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.z]

    @staticmethod
    def from_list(values: list[float]) -> "Point":
        if len(values) == 2:
            x, y = values
            z = 0.0
        elif len(values) == 3:
            x, y, z = values
        else:
            raise ValueError(f"point needs 2 or 3 coordinates, got {values!r}")
        return Point(float(x), float(y), float(z))


@dataclass
class Zone:
    """A named polygonal area of space (e.g. a room, hallway, floor section)."""

    id: str
    name: str
    polygon: list[Point]
    floor: int = 0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "polygon": [p.to_list() for p in self.polygon],
            "floor": self.floor,
            "properties": self.properties,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Zone":
        return Zone(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            polygon=[Point.from_list(v) for v in data["polygon"]],
            floor=int(data.get("floor", 0)),
            properties=dict(data.get("properties", {})),
        )


@dataclass
class Entity:
    """A thing placed in space (sensor, furniture, robot, person, ...).

    `position`/`zone_id` are the believed location; `state` holds other
    believed attributes (status, availability, condition, assignee, ...).
    Both change ONLY via observations (see RealityWorld.apply_observation),
    never directly by actions. `state_provenance` records, per attribute,
    the observation that justifies the current value.
    """

    id: str
    name: str
    kind: str
    position: Point
    zone_id: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    state_provenance: dict[str, Provenance] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "position": self.position.to_list(),
            "zone_id": self.zone_id,
            "properties": self.properties,
            "state": self.state,
            "state_provenance": {
                k: v.to_dict() for k, v in self.state_provenance.items()
            },
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Entity":
        return Entity(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            kind=str(data.get("kind", "object")),
            position=Point.from_list(data["position"]),
            zone_id=data.get("zone_id"),
            properties=dict(data.get("properties", {})),
            state=dict(data.get("state", {})),
            state_provenance={
                k: Provenance.from_dict(v)
                for k, v in data.get("state_provenance", {}).items()
            },
        )


@dataclass
class SpatialWorld:
    """The full spatial model: zones, entities, and zone connectivity."""

    zones: dict[str, Zone] = field(default_factory=dict)
    entities: dict[str, Entity] = field(default_factory=dict)
    # adjacency: zone_id -> list of directly connected zone_ids (doors, openings)
    adjacency: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "zones": [z.to_dict() for z in self.zones.values()],
            "entities": [e.to_dict() for e in self.entities.values()],
            "adjacency": self.adjacency,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SpatialWorld":
        zones = {z["id"]: Zone.from_dict(z) for z in data.get("zones", [])}
        entities = {e["id"]: Entity.from_dict(e) for e in data.get("entities", [])}
        adjacency = {k: list(v) for k, v in data.get("adjacency", {}).items()}
        return SpatialWorld(zones=zones, entities=entities, adjacency=adjacency)


# ---------------------------------------------------------------------------
# REALITY v0: action/state layer models
#
# The spatial models above answer "what is where". The models below answer
# "what is true, what happened, what can be done, and what was verified".
# ---------------------------------------------------------------------------


@dataclass
class Provenance:
    """Why the system believes an attribute value: the observation behind it."""

    observed_at: float
    source: str  # observation source id, e.g. "sim-camera-1"
    confidence: float  # 0.0 .. 1.0
    observation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at,
            "source": self.source,
            "confidence": self.confidence,
            "observation_id": self.observation_id,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Provenance":
        return Provenance(
            observed_at=float(data["observed_at"]),
            source=str(data["source"]),
            confidence=float(data.get("confidence", 1.0)),
            observation_id=data.get("observation_id"),
        )


@dataclass
class Relationship:
    """How two entities relate: inside, adjacent, connected_to, owned_by,
    assigned_to, blocking, near, depends_on."""

    subject_id: str
    predicate: str
    object_id: str
    provenance: Provenance | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "object_id": self.object_id,
            "provenance": self.provenance.to_dict()
            if self.provenance
            else None,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Relationship":
        prov = data.get("provenance")
        return Relationship(
            subject_id=str(data["subject_id"]),
            predicate=str(data["predicate"]),
            object_id=str(data["object_id"]),
            provenance=Provenance.from_dict(prov) if prov else None,
        )


@dataclass
class Observation:
    """Evidence about reality: a source reports attribute values for an
    entity at a time, with a confidence. Observations are the ONLY thing
    that changes the world's believed state — never actions directly."""

    id: str
    ts: float
    source: str  # e.g. "sim-camera-1", "gps", "human-report", "api-event"
    entity_id: str
    observed_state: dict[str, Any]  # attr -> value; may include zone_id/position
    confidence: float = 1.0
    context: str = ""  # free-form location/context note

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "source": self.source,
            "entity_id": self.entity_id,
            "observed_state": self.observed_state,
            "confidence": self.confidence,
            "context": self.context,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Observation":
        return Observation(
            id=str(data["id"]),
            ts=float(data["ts"]),
            source=str(data["source"]),
            entity_id=str(data["entity_id"]),
            observed_state=dict(data.get("observed_state", {})),
            confidence=float(data.get("confidence", 1.0)),
            context=str(data.get("context", "")),
        )


@dataclass
class Event:
    """Something that happened: a state transition, an observation arrival,
    or an action lifecycle transition. Append-only; the source of truth for
    temporal queries ("what changed?", "why?")."""

    id: str
    ts: float
    type: str  # observation_recorded, state_changed, action_proposed, ...
    entity_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    caused_by: dict[str, str] | None = None  # {"kind": "observation"|"action", "id": ...}
    actor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "type": self.type,
            "entity_id": self.entity_id,
            "details": self.details,
            "caused_by": self.caused_by,
            "actor": self.actor,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Event":
        return Event(
            id=str(data["id"]),
            ts=float(data["ts"]),
            type=str(data["type"]),
            entity_id=data.get("entity_id"),
            details=dict(data.get("details", {})),
            caused_by=data.get("caused_by"),
            actor=data.get("actor"),
        )


# Action lifecycle statuses. An action is never just "action() -> success":
# the engine walks proposed -> authorized -> executing -> executed ->
# observed -> verified (or failed / rejected), and every transition is an event.
ACTION_PROPOSED = "proposed"
ACTION_AUTHORIZED = "authorized"
ACTION_EXECUTING = "executing"
ACTION_EXECUTED = "executed"
ACTION_OBSERVED = "observed"
ACTION_VERIFIED = "verified"
ACTION_PARTIALLY_VERIFIED = "partially_verified"
ACTION_FAILED = "failed"
ACTION_REJECTED = "rejected"


@dataclass
class Action:
    """Something an AI or external system attempts to do in the world.

    The lifecycle distinguishes "I planned it" (proposed) from "it was
    allowed" (authorized) from "the executor claims it ran" (executed) from
    "I independently observed the outcome" (observed) from "the outcome
    matches what was expected" (verified).
    """

    id: str
    type: str  # move_entity, reserve_resource, change_status, assign_entity, notify
    actor: str  # who requested it: agent id, user, system
    target: str  # entity id the action operates on
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = ACTION_PROPOSED
    authorization: dict[str, Any] | None = None  # {"approved_by": ..., "approved_at": ...}
    created_at: float = 0.0
    authorized_at: float | None = None
    executed_at: float | None = None
    observed_at: float | None = None
    verified_at: float | None = None
    expected_effect: dict[str, dict[str, Any]] = field(default_factory=dict)
    actual_effect: dict[str, dict[str, Any]] = field(default_factory=dict)
    executor_report: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] | None = None
    rejection_reason: str | None = None  # set when status becomes rejected
    provenance: str = ""  # where the request came from: "cli", "ask", "demo", ...

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "actor": self.actor,
            "target": self.target,
            "parameters": self.parameters,
            "status": self.status,
            "authorization": self.authorization,
            "created_at": self.created_at,
            "authorized_at": self.authorized_at,
            "executed_at": self.executed_at,
            "observed_at": self.observed_at,
            "verified_at": self.verified_at,
            "expected_effect": self.expected_effect,
            "actual_effect": self.actual_effect,
            "executor_report": self.executor_report,
            "verification": self.verification,
            "rejection_reason": self.rejection_reason,
            "provenance": self.provenance,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Action":
        return Action(
            id=str(data["id"]),
            type=str(data["type"]),
            actor=str(data.get("actor", "unknown")),
            target=str(data["target"]),
            parameters=dict(data.get("parameters", {})),
            status=str(data.get("status", ACTION_PROPOSED)),
            authorization=data.get("authorization"),
            created_at=float(data.get("created_at", 0.0)),
            authorized_at=data.get("authorized_at"),
            executed_at=data.get("executed_at"),
            observed_at=data.get("observed_at"),
            verified_at=data.get("verified_at"),
            expected_effect={
                k: dict(v) for k, v in data.get("expected_effect", {}).items()
            },
            actual_effect={
                k: dict(v) for k, v in data.get("actual_effect", {}).items()
            },
            executor_report=dict(data.get("executor_report", {})),
            verification=data.get("verification"),
            rejection_reason=data.get("rejection_reason"),
            provenance=str(data.get("provenance", "")),
        )


@dataclass
class Constraint:
    """A rule limiting what actions are allowed: permissions, safety,
    geographic boundaries, resource limits, human approval, time windows."""

    id: str
    name: str
    kind: str  # permission, safety, boundary, resource, approval, time
    description: str = ""
    applies_to: list[str] = field(default_factory=list)  # action types
    check: str = ""  # registry key in reality.core.constraints.CHECKS
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "applies_to": self.applies_to,
            "check": self.check,
            "parameters": self.parameters,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Constraint":
        return Constraint(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            kind=str(data.get("kind", "safety")),
            description=str(data.get("description", "")),
            applies_to=list(data.get("applies_to", [])),
            check=str(data.get("check", "")),
            parameters=dict(data.get("parameters", {})),
        )
