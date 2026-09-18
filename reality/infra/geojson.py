"""GeoJSON import/export for the spatial substrate.

Converts a SpatialWorld to a GeoJSON FeatureCollection and back, so worlds
can move between REALITY and GIS tooling (QGIS, geojson.io, PostGIS, web
maps) without a custom format:

  zones    -> Feature { geometry: Polygon,   properties: {kind: "zone", ...} }
  entities -> Feature { geometry: Point,     properties: {kind: "entity", ...} }

Zone adjacency is not geometric; it rides along as a foreign member
("reality": {"adjacency": ...}) on the FeatureCollection, which RFC 7946
explicitly permits. Coordinates are [x, y], with z appended only when the
geometry actually uses it.

Only the spatial substrate travels — beliefs, events, actions and
constraints are the world-state layer's business and are not serialized
here. Use JsonFileWorldStore for full snapshots.
"""

from __future__ import annotations

import json
from typing import Any

from reality.core.models import Entity, Point, SpatialWorld, Zone

GEOJSON_TYPE = "FeatureCollection"
_REAILITY_MEMBER = "reality"


class GeoJSONError(ValueError):
    """Raised when GeoJSON input fails validation."""


def _position(p: Point) -> list[float]:
    return [p.x, p.y] if p.z == 0 else [p.x, p.y, p.z]


def _close_ring(coords: list[list[float]]) -> list[list[float]]:
    if coords and coords[0] != coords[-1]:
        return coords + [coords[0]]
    return coords


def zone_to_feature(zone: Zone) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                _close_ring([_position(p) for p in zone.polygon])
            ],
        },
        "properties": {
            "kind": "zone",
            "id": zone.id,
            "name": zone.name,
            "floor": zone.floor,
            "properties": zone.properties,
        },
    }


def entity_to_feature(entity: Entity) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": _position(entity.position)},
        "properties": {
            "kind": "entity",
            "id": entity.id,
            "name": entity.name,
            "entity_kind": entity.kind,
            "zone_id": entity.zone_id,
            "properties": entity.properties,
            "state": entity.state,
        },
    }


def world_to_geojson(world: SpatialWorld) -> dict[str, Any]:
    """Serialize the spatial substrate to a GeoJSON FeatureCollection."""
    return {
        "type": GEOJSON_TYPE,
        "features": (
            [zone_to_feature(z) for z in world.zones.values()]
            + [entity_to_feature(e) for e in world.entities.values()]
        ),
        _REAILITY_MEMBER: {"adjacency": world.adjacency},
    }


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise GeoJSONError(message)


def _parse_positions(coords: Any, what: str) -> list[Point]:
    _require(
        isinstance(coords, list) and len(coords) >= 1,
        f"{what}: coordinates must be a non-empty list",
    )
    points = []
    for c in coords:
        _require(
            isinstance(c, (list, tuple)) and 2 <= len(c) <= 3,
            f"{what}: each position needs 2 or 3 numbers, got {c!r}",
        )
        try:
            points.append(Point(float(c[0]), float(c[1]),
                                float(c[2]) if len(c) == 3 else 0.0))
        except (TypeError, ValueError):
            raise GeoJSONError(
                f"{what}: position coordinates must be numbers, got {c!r}"
            )
    return points


def _feature_zone(feature: dict, index: int) -> Zone:
    what = f"feature #{index}"
    props = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    _require(geom.get("type") == "Polygon",
             f"{what}: zone feature needs Polygon geometry")
    rings = geom.get("coordinates")
    _require(isinstance(rings, list) and len(rings) >= 1,
             f"{what}: Polygon needs at least one ring")
    ring = list(rings[0])
    if len(ring) >= 2 and ring[0] == ring[-1]:
        ring = ring[:-1]  # drop the GeoJSON closing duplicate
    _require(len(ring) >= 3,
             f"{what}: zone polygon needs at least 3 distinct points")
    _require("id" in props, f"{what}: zone feature needs properties.id")
    return Zone(
        id=str(props["id"]),
        name=str(props.get("name", props["id"])),
        polygon=_parse_positions(ring, what),
        floor=int(props.get("floor", 0)),
        properties=dict(props.get("properties", {}) or {}),
    )


def _feature_entity(feature: dict, index: int) -> Entity:
    what = f"feature #{index}"
    props = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    _require(geom.get("type") == "Point",
             f"{what}: entity feature needs Point geometry")
    _require("id" in props, f"{what}: entity feature needs properties.id")
    return Entity(
        id=str(props["id"]),
        name=str(props.get("name", props["id"])),
        kind=str(props.get("entity_kind", "object")),
        position=_parse_positions([geom.get("coordinates")], what)[0],
        zone_id=props.get("zone_id"),
        properties=dict(props.get("properties", {}) or {}),
        state=dict(props.get("state", {}) or {}),
    )


def geojson_to_world(data: dict[str, Any]) -> SpatialWorld:
    """Parse a GeoJSON FeatureCollection (as produced by world_to_geojson,
    or hand-written GIS data) back into a SpatialWorld.

    Raises GeoJSONError on malformed input. Zones and entities keep their
    ids; duplicate ids raise GeoJSONError.
    """
    _require(isinstance(data, dict), "GeoJSON must be a JSON object")
    _require(data.get("type") == GEOJSON_TYPE,
             f"GeoJSON type must be {GEOJSON_TYPE!r}")
    features = data.get("features")
    _require(isinstance(features, list), "GeoJSON needs a features list")

    world = SpatialWorld()
    for i, feature in enumerate(features):
        _require(isinstance(feature, dict), f"feature #{i} must be an object")
        _require(feature.get("type") == "Feature",
                 f"feature #{i} must have type 'Feature'")
        kind = (feature.get("properties") or {}).get("kind")
        if kind == "zone":
            zone = _feature_zone(feature, i)
            _require(zone.id not in world.zones,
                     f"duplicate zone id {zone.id!r}")
            world.zones[zone.id] = zone
        elif kind == "entity":
            entity = _feature_entity(feature, i)
            _require(entity.id not in world.entities,
                     f"duplicate entity id {entity.id!r}")
            world.entities[entity.id] = entity
        else:
            raise GeoJSONError(
                f"feature #{i}: properties.kind must be 'zone' or 'entity', "
                f"got {kind!r}"
            )

    member = data.get(_REAILITY_MEMBER) or {}
    adjacency = member.get("adjacency", {})
    _require(isinstance(adjacency, dict), "'reality.adjacency' must be an object")
    world.adjacency = {str(k): [str(n) for n in v]
                       for k, v in adjacency.items()}
    return world


def world_to_geojson_str(world: SpatialWorld, *, indent: int = 2) -> str:
    return json.dumps(world_to_geojson(world), indent=indent)


def geojson_to_world_str(text: str) -> SpatialWorld:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeoJSONError(f"invalid JSON: {exc}") from exc
    return geojson_to_world(data)


def save_geojson(world: SpatialWorld, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(world_to_geojson_str(world))


def load_geojson(path: str) -> SpatialWorld:
    with open(path, encoding="utf-8") as f:
        return geojson_to_world_str(f.read())
