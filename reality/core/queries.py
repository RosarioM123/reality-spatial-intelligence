"""Natural-language query layer over the spatial pipeline.

`ask(pipeline, text)` parses a small set of spatial question patterns and
returns a JSON-serializable answer dict — the "AI-native" interface: an LLM
can call these primitives as tools, or pass user phrasing straight through.

Supported patterns (case-insensitive):
  - "where is <entity>"
  - "what is near <entity> [within <radius>]"
  - "nearest <kind> [to <entity>]"
  - "route from <zone-a> to <zone-b>" / "how do I get from <a> to <b>"
  - "what zone is at (<x>, <y>)" / "what zone is <x>, <y> in"
  - "list zones" / "list entities [of kind <kind>]"
  - "describe <zone>"
"""

from __future__ import annotations

import re

from reality.config import get_settings
from reality.core.models import Entity, Point
from reality.core.pipeline import SpatialPipeline


def _find_entity(pipeline: SpatialPipeline, ref: str) -> Entity | None:
    ref = ref.strip().lower()
    for entity in pipeline.world.entities.values():
        if entity.id.lower() == ref or entity.name.lower() == ref:
            return entity
    return None


def _find_zone_id(pipeline: SpatialPipeline, ref: str) -> str | None:
    ref = ref.strip().lower()
    for zid, zone in pipeline.world.zones.items():
        if zid.lower() == ref or zone.name.lower() == ref:
            return zid
    return None


def _entity_summary(e: Entity) -> dict:
    d = e.to_dict()
    d["position"] = {"x": e.position.x, "y": e.position.y, "z": e.position.z}
    return d


def ask(pipeline: SpatialPipeline, text: str) -> dict:
    q = text.strip()
    low = q.lower()
    settings = get_settings()

    m = re.match(r"where is (.+?)\??$", low)
    if m:
        entity = _find_entity(pipeline, m.group(1))
        if entity is None:
            return {"type": "not_found", "query": q,
                    "message": f"no entity matching {m.group(1).strip()!r}"}
        zone = pipeline.locate(entity.position)
        return {"type": "entity_location", "query": q,
                "entity": _entity_summary(entity),
                "zone_id": zone.id if zone else None,
                "zone_name": zone.name if zone else None}

    m = re.match(r"what(?:'s| is) near (.+?)(?: within ([\d.]+))?\??$", low)
    if m:
        entity = _find_entity(pipeline, m.group(1))
        if entity is None:
            return {"type": "not_found", "query": q,
                    "message": f"no entity matching {m.group(1).strip()!r}"}
        radius = float(m.group(2)) if m.group(2) else settings.default_radius
        hits = [h for h in pipeline.near(entity.position, radius)
                if h["entity"]["id"] != entity.id][: settings.max_results]
        return {"type": "nearby", "query": q,
                "origin": _entity_summary(entity), "radius": radius,
                "results": hits}

    m = re.match(r"nearest (\w[\w ]*?)(?: to (.+?))?\??$", low)
    if m:
        kind, ref = m.group(1).strip(), m.group(2)
        if ref:
            entity = _find_entity(pipeline, ref)
            if entity is None:
                return {"type": "not_found", "query": q,
                        "message": f"no entity matching {ref.strip()!r}"}
            origin = entity.position
            origin_ref = entity.id
        else:
            origin, origin_ref = Point(0, 0), "origin (0, 0)"
        hit = pipeline.nearest(origin, kind=kind)
        if hit is None:
            return {"type": "not_found", "query": q,
                    "message": f"no entity of kind {kind!r}"}
        return {"type": "nearest", "query": q, "kind": kind,
                "origin": origin_ref, "result": hit}

    m = re.match(
        r"(?:route|path|how do i get) from (.+?) to (.+?)\??$", low)
    if m:
        from_id = _find_zone_id(pipeline, m.group(1))
        to_id = _find_zone_id(pipeline, m.group(2))
        if from_id is None or to_id is None:
            return {"type": "not_found", "query": q,
                    "message": "unknown zone in route request"}
        path = pipeline.route(from_id, to_id)
        if path is None:
            return {"type": "no_route", "query": q,
                    "from": from_id, "to": to_id,
                    "message": "no connected path between zones"}
        names = [pipeline.world.zones[z].name for z in path]
        return {"type": "route", "query": q, "from": from_id, "to": to_id,
                "path": path, "path_names": names,
                "hops": len(path) - 1}

    m = re.match(
        r"what zone is (?:at )?\(?(-?[\d.]+)\s*,\s*(-?[\d.]+)\)?(?: in)?\??$",
        low)
    if m:
        p = Point(float(m.group(1)), float(m.group(2)))
        zone = pipeline.locate(p)
        if zone is None:
            return {"type": "no_zone", "query": q,
                    "point": p.to_list(),
                    "message": "point is not inside any known zone"}
        return {"type": "zone_at", "query": q, "point": p.to_list(),
                "zone_id": zone.id, "zone_name": zone.name}

    m = re.match(r"list (zones|entities)(?: of kind (\w+))?\??$", low)
    if m:
        if m.group(1) == "zones":
            return {"type": "zone_list", "query": q,
                    "zones": [z.to_dict()
                              for z in pipeline.world.zones.values()]}
        kind = m.group(2)
        entities = [e for e in pipeline.world.entities.values()
                    if kind is None or e.kind == kind]
        return {"type": "entity_list", "query": q, "kind": kind,
                "entities": [_entity_summary(e) for e in entities]}

    m = re.match(r"describe (.+?)\??$", low)
    if m:
        zid = _find_zone_id(pipeline, m.group(1))
        if zid is None:
            return {"type": "not_found", "query": q,
                    "message": f"no zone matching {m.group(1).strip()!r}"}
        return {"type": "zone_detail", "query": q,
                "detail": pipeline.describe_zone(zid)}

    return {"type": "unrecognized", "query": q,
            "message": "could not parse as a spatial question",
            "hint": "try: 'where is <entity>', 'what is near <entity>', "
                    "'nearest <kind> to <entity>', 'route from <a> to <b>', "
                    "'what zone is at (x, y)', 'list zones'"}
