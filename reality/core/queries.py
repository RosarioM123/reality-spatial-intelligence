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
from typing import Any

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
            return {
                "type": "not_found",
                "query": q,
                "message": f"no entity matching {m.group(1).strip()!r}",
            }
        zone = pipeline.locate(entity.position)
        return {
            "type": "entity_location",
            "query": q,
            "entity": _entity_summary(entity),
            "zone_id": zone.id if zone else None,
            "zone_name": zone.name if zone else None,
        }

    m = re.match(r"what(?:'s| is) near (.+?)(?: within ([\d.]+))?\??$", low)
    if m:
        entity = _find_entity(pipeline, m.group(1))
        if entity is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no entity matching {m.group(1).strip()!r}",
            }
        radius = float(m.group(2)) if m.group(2) else settings.default_radius
        hits = [
            h
            for h in pipeline.near(entity.position, radius)
            if h["entity"]["id"] != entity.id
        ][: settings.max_results]
        return {
            "type": "nearby",
            "query": q,
            "origin": _entity_summary(entity),
            "radius": radius,
            "results": hits,
        }

    m = re.match(r"nearest (\w[\w ]*?)(?: to (.+?))?\??$", low)
    if m:
        kind, ref = m.group(1).strip(), m.group(2)
        if ref:
            entity = _find_entity(pipeline, ref)
            if entity is None:
                return {
                    "type": "not_found",
                    "query": q,
                    "message": f"no entity matching {ref.strip()!r}",
                }
            origin = entity.position
            origin_ref = entity.id
        else:
            origin, origin_ref = Point(0, 0), "origin (0, 0)"
        hit = pipeline.nearest(origin, kind=kind)
        if hit is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no entity of kind {kind!r}",
            }
        return {
            "type": "nearest",
            "query": q,
            "kind": kind,
            "origin": origin_ref,
            "result": hit,
        }

    m = re.match(r"(?:route|path|how do i get) from (.+?) to (.+?)\??$", low)
    if m:
        from_id = _find_zone_id(pipeline, m.group(1))
        to_id = _find_zone_id(pipeline, m.group(2))
        if from_id is None or to_id is None:
            return {
                "type": "not_found",
                "query": q,
                "message": "unknown zone in route request",
            }
        path = pipeline.route(from_id, to_id)
        if path is None:
            return {
                "type": "no_route",
                "query": q,
                "from": from_id,
                "to": to_id,
                "message": "no connected path between zones",
            }
        names = [pipeline.world.zones[z].name for z in path]
        return {
            "type": "route",
            "query": q,
            "from": from_id,
            "to": to_id,
            "path": path,
            "path_names": names,
            "hops": len(path) - 1,
        }

    m = re.match(
        r"what zone is (?:at )?\(?(-?[\d.]+)\s*,\s*(-?[\d.]+)\)?(?: in)?\??$", low
    )
    if m:
        p = Point(float(m.group(1)), float(m.group(2)))
        zone = pipeline.locate(p)
        if zone is None:
            return {
                "type": "no_zone",
                "query": q,
                "point": p.to_list(),
                "message": "point is not inside any known zone",
            }
        return {
            "type": "zone_at",
            "query": q,
            "point": p.to_list(),
            "zone_id": zone.id,
            "zone_name": zone.name,
        }

    m = re.match(r"list (zones|entities)(?: of kind (\w+))?\??$", low)
    if m:
        if m.group(1) == "zones":
            return {
                "type": "zone_list",
                "query": q,
                "zones": [z.to_dict() for z in pipeline.world.zones.values()],
            }
        kind = m.group(2)
        entities = [
            e
            for e in pipeline.world.entities.values()
            if kind is None or e.kind == kind
        ]
        return {
            "type": "entity_list",
            "query": q,
            "kind": kind,
            "entities": [_entity_summary(e) for e in entities],
        }

    m = re.match(r"describe (.+?)\??$", low)
    if m:
        zid = _find_zone_id(pipeline, m.group(1))
        if zid is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no zone matching {m.group(1).strip()!r}",
            }
        return {
            "type": "zone_detail",
            "query": q,
            "detail": pipeline.describe_zone(zid),
        }

    return {
        "type": "unrecognized",
        "query": q,
        "message": "could not parse as a spatial question",
        "hint": "try: 'where is <entity>', 'what is near <entity>', "
        "'nearest <kind> to <entity>', 'route from <a> to <b>', "
        "'what zone is at (x, y)', 'list zones'",
    }


# ---------------------------------------------------------------------------
# REALITY v0: ask_world() — the AI-native interface over the full world model.
#
# ask() above answers static "what is where" questions. ask_world() adds the
# temporal / action / verification layer: state, history, evidence,
# capabilities, plans, and — when given a runtime (e.g. Simulation) —
# executing the full propose -> authorize -> execute -> observe -> verify
# loop. Everything returned is JSON-serializable.
# ---------------------------------------------------------------------------

from reality.core import constraints as _constraints
from reality.core.actions import ActionEngine
from reality.core.models import (  # noqa: F401  (Observation re-exported for docs)
    ACTION_PROPOSED,
    Action,
    Observation,
)
from reality.core.world import RealityWorld


def _find_entity_w(world: RealityWorld, ref: str):
    ref = ref.strip().lower()
    for entity in world.spatial.entities.values():
        if entity.id.lower() == ref or entity.name.lower() == ref:
            return entity
    return None


def _entity_full(world: RealityWorld, entity) -> dict:
    d = _entity_summary(entity)
    d["state"] = dict(entity.state)
    d["provenance"] = {k: v.to_dict() for k, v in entity.state_provenance.items()}
    return d


def _event_summary(world: RealityWorld, e) -> dict:
    return {
        "id": e.id,
        "ts": e.ts,
        "type": e.type,
        "entity_id": e.entity_id,
        "actor": e.actor,
        "details": e.details,
        "caused_by": e.caused_by,
    }


def _plan_workstation(
    world: RealityWorld,
    team_ref: str,
    person: str | None,
    runtime=None,
    approved_by: str | None = None,
) -> dict:
    team = _find_entity_w(world, team_ref)
    if team is None or team.kind != "team":
        # Fall back to any entity matching the ref (e.g. a zone name).
        team = _find_entity_w(world, team_ref)
        if team is None:
            return {"type": "not_found", "message": f"no team matching {team_ref!r}"}
    origin = team.position
    candidates = [
        e
        for e in world.spatial.entities.values()
        if e.kind == "workstation" and e.state.get("availability") == "available"
    ]
    from reality.core import geometry as _g

    ranked = sorted(candidates, key=lambda e: _g.distance(e.position, origin))
    if not ranked:
        return {"type": "no_workstation", "message": "no available workstation found"}
    pick = ranked[0]
    steps: list[dict[str, Any]] = [
        {
            "action": "reserve_resource",
            "target": pick.id,
            "parameters": {"for_whom": person or "unassigned"},
        },
        {
            "action": "assign_entity",
            "target": pick.id,
            "parameters": {"assignee": person or "unassigned"},
        },
    ]
    # Pre-check constraints for each planned step. We evaluate a probe
    # Action directly (never proposed): planning must not pollute the
    # world's actions or event log.
    for step in steps:
        probe = Action(
            id=f"probe-{step['action']}-{step['target']}",
            type=step["action"],
            actor="ask",
            target=step["target"],
            parameters=step["parameters"],
            status=ACTION_PROPOSED,
            created_at=world.now(),
            provenance="ask-plan",
        )
        results = _constraints.evaluate(probe, world)
        step["constraint_check"] = [
            {"constraint": c.id, "ok": ok, "reason": reason}
            for c, ok, reason in results
        ]
        step["blocked"] = any(not ok for _, ok, _ in results)

    result: dict = {
        "type": "workstation_plan",
        "team": team.id,
        "team_zone": team.zone_id,
        "chosen": _entity_full(world, pick),
        "distance_to_team": round(_g.distance(pick.position, origin), 3),
        "alternatives": [e.id for e in ranked[1:3]],
        "plan": steps,
    }
    if person and runtime is not None:
        executed = []
        for step in steps:
            if step["blocked"]:
                executed.append({"step": step, "skipped": "blocked"})
                continue
            action = runtime.act(
                step["action"],
                actor="ask",
                target=step["target"],
                parameters=step["parameters"],
                provenance="ask",
                approved_by=approved_by,
            )
            executed.append(action.to_dict())
        result["execution"] = executed
    elif person:
        result["execution"] = (
            "not executed: no runtime attached "
            "(load the world in a Simulation to execute)"
        )
    else:
        result["execution"] = (
            "plan only: no person named; add 'and prepare it for <name>' to execute"
        )
    return result


def ask_world(
    world: RealityWorld, text: str, runtime=None, approved_by: str | None = None
) -> dict:
    """Ask anything about the world: state, history, evidence, capabilities,
    plans, and actions. `runtime` (e.g. Simulation) enables execution;
    `approved_by` declares whose authority an executed action runs under
    (actions that need human approval stay proposed without it)."""
    q = text.strip()
    low = q.lower()

    m = re.match(r"what is the status of (.+?)\??$", low)
    if m:
        entity = _find_entity_w(world, m.group(1))
        if entity is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no entity matching {m.group(1).strip()!r}",
            }
        changes = world.history(entity.id)
        return {
            "type": "entity_status",
            "query": q,
            "entity": _entity_full(world, entity),
            "recent_changes": changes[-5:],
        }

    m = re.match(r"why is (.+?) (unavailable|reserved|occupied|failed|closed)\??$", low)
    if m:
        entity = _find_entity_w(world, m.group(1))
        if entity is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no entity matching {m.group(1).strip()!r}",
            }
        word = m.group(2)
        matching = [
            a
            for a, v in entity.state.items()
            if str(v).lower() == word or a == "availability"
        ]
        return {
            "type": "state_explanation",
            "query": q,
            "entity": _entity_full(world, entity),
            "matching_attributes": matching,
            "history": world.history(entity.id),
        }

    m = re.match(r"what changed(?: since ([\d.]+))?\??$", low)
    if m:
        since = float(m.group(1)) if m.group(1) else 0.0
        events = world.what_changed(since)
        return {
            "type": "changes",
            "query": q,
            "since": since,
            "count": len(events),
            "events": events[-10:],
        }

    m = re.match(r"history of (.+?)\??$", low)
    if m:
        entity = _find_entity_w(world, m.group(1))
        if entity is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no entity matching {m.group(1).strip()!r}",
            }
        return {
            "type": "history",
            "query": q,
            "entity_id": entity.id,
            "transitions": world.history(entity.id),
        }

    m = re.match(r"what evidence supports (.+?) being in (.+?)\??$", low)
    if m:
        entity = _find_entity_w(world, m.group(1))
        if entity is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no entity matching {m.group(1).strip()!r}",
            }
        zid = _find_zone_id(SpatialPipeline(world.spatial), m.group(2))
        evidence = world.evidence_for(entity.id, "zone_id")
        if evidence is not None:
            evidence["claimed_zone"] = zid
            evidence["consistent"] = entity.zone_id == zid
        return {"type": "evidence", "query": q, "evidence": evidence}

    m = re.match(r"what actions can i take(?: on (.+?)| in (.+?))?\??$", low)
    if m:
        engine = ActionEngine(world, executor=None)
        entity = _find_entity_w(world, m.group(1)) if m.group(1) else None
        if m.group(1) and entity is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no entity matching {m.group(1).strip()!r}",
            }
        entity_id = entity.id if entity else None
        zone_id = None
        if m.group(2):
            zone_id = _find_zone_id(SpatialPipeline(world.spatial), m.group(2))
        return {
            "type": "capabilities",
            "query": q,
            "available": engine.available_actions(entity_id=entity_id, zone_id=zone_id),
        }

    m = re.match(r"move (.+?) to (.+?)\??$", low)
    if m:
        entity = _find_entity_w(world, m.group(1))
        zid = _find_zone_id(SpatialPipeline(world.spatial), m.group(2))
        if entity is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no entity matching {m.group(1).strip()!r}",
            }
        if zid is None:
            return {
                "type": "not_found",
                "query": q,
                "message": f"no zone matching {m.group(2).strip()!r}",
            }
        if runtime is None:
            return {
                "type": "action_plan",
                "query": q,
                "plan": [
                    {
                        "action": "move_entity",
                        "target": entity.id,
                        "parameters": {"to_zone": zid},
                    }
                ],
                "note": "no runtime attached; nothing was executed",
            }
        try:
            action = runtime.act(
                "move_entity",
                actor="ask",
                target=entity.id,
                parameters={"to_zone": zid},
                provenance="ask",
                approved_by=approved_by,
            )
        except ValueError as exc:
            return {"type": "action_rejected", "query": q, "reason": str(exc)}
        return {"type": "action_result", "query": q, "action": action.to_dict()}

    m = re.match(r"(?:did|verify) (.+?) (succeed|fail)\??$", low) or re.match(
        r"verify (.+?)\??$", low
    )
    if m:
        aid = m.group(1).strip()
        action = world.actions.get(aid)
        if action is None:
            return {"type": "not_found", "query": q, "message": f"no action {aid!r}"}
        return {"type": "action_status", "query": q, "action": action.to_dict()}

    m = re.match(
        r"find (?:an )?available workstation near (.+?)"
        r"(?: and prepare (?:it )?for (.+?))?\??$",
        low,
    )
    if m:
        return _plan_workstation(
            world,
            m.group(1).strip(),
            m.group(2).strip() if m.group(2) else None,
            runtime,
            approved_by,
        )

    # Spatial fallback: delegate to the static pipeline, enriched with state.
    pipeline = SpatialPipeline(world.spatial)
    ans = ask(pipeline, text)
    if ans.get("type") == "entity_location":
        entity = _find_entity_w(world, ans["entity"]["id"])
        if entity is not None:
            ans["entity"] = _entity_full(world, entity)
            ans["evidence"] = world.evidence_for(entity.id, "zone_id")
    return ans
