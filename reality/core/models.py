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
    """A thing placed in space (sensor, furniture, robot, person, ...)."""

    id: str
    name: str
    kind: str
    position: Point
    zone_id: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "position": self.position.to_list(),
            "zone_id": self.zone_id,
            "properties": self.properties,
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
