"""Geofence alerts: zone enter/exit detection over entity tracks.

A GeofenceMonitor watches position updates and emits events when an entity
crosses a zone boundary. The use case is physical-world alerting ("the
forklift entered the packing zone", "the package left the building") built
on the same zone polygons the spatial pipeline already indexes.

Semantics:
  - The first sighting of an entity only establishes a baseline; it emits
    nothing (unless emit_initial=True). A monitor that cried "enter" for
    every entity already inside a zone on startup would be useless.
  - Moving directly from zone A to zone B emits exit(A) then enter(B), in
    that order — the exit is always reported before the enter.
  - Leaving all zones emits exit(zone). Re-entering later emits enter(zone).
  - Points on a zone boundary count as inside (matches
    geometry.point_in_polygon).
"""

from __future__ import annotations

from dataclasses import dataclass

from reality.core import geometry
from reality.core.models import Point, SpatialWorld, Zone

ENTER = "enter"
EXIT = "exit"


@dataclass(frozen=True)
class GeofenceEvent:
    """A zone-boundary crossing."""

    entity_id: str
    zone_id: str  # the zone entered or exited
    kind: str  # "enter" or "exit"
    ts: float

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "zone_id": self.zone_id,
            "kind": self.kind,
            "ts": self.ts,
        }


class GeofenceMonitor:
    """Tracks entity positions against zone polygons.

    `zones` may be a SpatialWorld or a plain {zone_id: Zone} mapping.
    """

    def __init__(
        self,
        zones: SpatialWorld | dict[str, Zone],
        *,
        emit_initial: bool = False,
    ):
        self.zones = zones.zones if isinstance(zones, SpatialWorld) else zones
        self.emit_initial = emit_initial
        self._bboxes = {
            zid: geometry.bounding_box(z.polygon) for zid, z in self.zones.items()
        }
        # entity_id -> zone_id | None (None = in no zone / unseen)
        self._last_zone: dict[str, str | None] = {}
        self._seen: set[str] = set()

    def locate(self, point: Point) -> Zone | None:
        """Zone containing the point, or None (first match wins)."""
        for zid, zone in self.zones.items():
            min_x, min_y, max_x, max_y = self._bboxes[zid]
            if not (min_x <= point.x <= max_x and min_y <= point.y <= max_y):
                continue
            if geometry.point_in_polygon(point, zone.polygon):
                return zone
        return None

    def current_zone(self, entity_id: str) -> str | None:
        """Last known zone of an entity (None if in no zone or unseen)."""
        return self._last_zone.get(entity_id)

    def update(self, entity_id: str, point: Point, ts: float) -> list[GeofenceEvent]:
        """Feed a position fix; returns any boundary-crossing events."""
        zone = self.locate(point)
        zone_id = zone.id if zone else None
        events: list[GeofenceEvent] = []

        if entity_id not in self._seen:
            self._seen.add(entity_id)
            self._last_zone[entity_id] = zone_id
            if self.emit_initial and zone_id is not None:
                events.append(GeofenceEvent(entity_id, zone_id, ENTER, ts))
            return events

        previous = self._last_zone.get(entity_id)
        if previous != zone_id:
            if previous is not None:
                events.append(GeofenceEvent(entity_id, previous, EXIT, ts))
            if zone_id is not None:
                events.append(GeofenceEvent(entity_id, zone_id, ENTER, ts))
            self._last_zone[entity_id] = zone_id
        return events

    def reset(self, entity_id: str | None = None) -> None:
        """Forget tracking state (one entity, or all when omitted)."""
        if entity_id is None:
            self._last_zone.clear()
            self._seen.clear()
        else:
            self._last_zone.pop(entity_id, None)
            self._seen.discard(entity_id)
