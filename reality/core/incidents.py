"""Incident management: the ops layer on top of telemetry.

Detection is only half the job. When a robot goes dark, leaves its zone,
or reports a fault, someone (or something) has to own the response. This
module tracks incidents through their lifecycle:

    open -> acknowledged -> resolved

with an append-only timeline of everything that happened. Incidents can
be raised manually or auto-created from telemetry alerts and geofence
violations — the detection sources don't need to know about each other,
they just report what they see.

Severity: info < warning < critical. An incident's severity is the max
of its source severities; it never decreases on its own.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# Lifecycle states.
INCIDENT_OPEN = "open"
INCIDENT_ACKNOWLEDGED = "acknowledged"
INCIDENT_RESOLVED = "resolved"

# Severity levels.
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

_SEVERITY_RANK = {SEVERITY_INFO: 0, SEVERITY_WARNING: 1, SEVERITY_CRITICAL: 2}

# What triggered the incident.
SOURCE_TELEMETRY = "telemetry"
SOURCE_GEOFENCE = "geofence"
SOURCE_MANUAL = "manual"
SOURCE_TASK = "task"


@dataclass
class TimelineEvent:
    """One append-only entry in an incident's history."""

    timestamp: float
    kind: str  # "created" | "note" | "acknowledged" | "resolved" | "escalated"
    message: str
    actor: str = "system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "kind": self.kind,
            "message": self.message,
            "actor": self.actor,
        }


@dataclass
class Incident:
    """A tracked operational incident."""

    id: str
    title: str
    robot_id: str | None
    source: str
    severity: str = SEVERITY_WARNING
    status: str = INCIDENT_OPEN
    timeline: list[TimelineEvent] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    resolved_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "robot_id": self.robot_id,
            "source": self.source,
            "severity": self.severity,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "timeline": [e.to_dict() for e in self.timeline],
        }


class IncidentManager:
    """Tracks incidents for a fleet."""

    def __init__(self):
        self.incidents: dict[str, Incident] = {}
        # Dedup key -> incident id, so repeated detections of the same
        # underlying problem don't spam new incidents.
        self._dedup: dict[str, str] = {}

    # -- lifecycle ------------------------------------------------------

    def raise_incident(
        self,
        title: str,
        robot_id: str | None = None,
        source: str = SOURCE_MANUAL,
        severity: str = SEVERITY_WARNING,
        dedup_key: str | None = None,
        actor: str = "system",
    ) -> Incident:
        """Raise an incident. If dedup_key matches an unresolved incident,
        the existing one is returned (escalated if more severe)."""
        if dedup_key and dedup_key in self._dedup:
            existing = self.incidents.get(self._dedup[dedup_key])
            if existing and existing.status != INCIDENT_RESOLVED:
                self._escalate(existing, severity, actor)
                return existing

        incident = Incident(
            id=f"inc-{uuid.uuid4().hex[:8]}",
            title=title,
            robot_id=robot_id,
            source=source,
            severity=severity,
        )
        incident.timeline.append(
            TimelineEvent(
                timestamp=time.time(),
                kind="created",
                message=f"Incident raised from {source}: {title}",
                actor=actor,
            )
        )
        self.incidents[incident.id] = incident
        if dedup_key:
            self._dedup[dedup_key] = incident.id
        return incident

    def acknowledge(self, incident_id: str, actor: str, note: str = "") -> Incident:
        incident = self._get(incident_id)
        if incident.status == INCIDENT_RESOLVED:
            raise ValueError(f"incident {incident_id} is already resolved")
        incident.status = INCIDENT_ACKNOWLEDGED
        incident.timeline.append(
            TimelineEvent(
                timestamp=time.time(),
                kind="acknowledged",
                message=note or f"Acknowledged by {actor}",
                actor=actor,
            )
        )
        return incident

    def add_note(
        self, incident_id: str, message: str, actor: str = "system"
    ) -> Incident:
        incident = self._get(incident_id)
        incident.timeline.append(
            TimelineEvent(
                timestamp=time.time(), kind="note", message=message, actor=actor
            )
        )
        return incident

    def resolve(self, incident_id: str, actor: str, note: str = "") -> Incident:
        incident = self._get(incident_id)
        if incident.status == INCIDENT_RESOLVED:
            raise ValueError(f"incident {incident_id} is already resolved")
        incident.status = INCIDENT_RESOLVED
        incident.resolved_at = time.time()
        incident.timeline.append(
            TimelineEvent(
                timestamp=time.time(),
                kind="resolved",
                message=note or f"Resolved by {actor}",
                actor=actor,
            )
        )
        return incident

    # -- queries ----------------------------------------------------------

    def open_incidents(self) -> list[Incident]:
        return [i for i in self.incidents.values() if i.status != INCIDENT_RESOLVED]

    def for_robot(self, robot_id: str) -> list[Incident]:
        return [i for i in self.incidents.values() if i.robot_id == robot_id]

    def summary(self) -> dict[str, Any]:
        open_ = self.open_incidents()
        by_severity: dict[str, int] = {}
        for i in open_:
            by_severity[i.severity] = by_severity.get(i.severity, 0) + 1
        return {
            "total": len(self.incidents),
            "open": len(open_),
            "by_severity": by_severity,
        }

    # -- internals --------------------------------------------------------

    def _get(self, incident_id: str) -> Incident:
        incident = self.incidents.get(incident_id)
        if incident is None:
            raise KeyError(f"unknown incident {incident_id!r}")
        return incident

    def _escalate(self, incident: Incident, severity: str, actor: str) -> None:
        if _SEVERITY_RANK[severity] > _SEVERITY_RANK[incident.severity]:
            incident.severity = severity
            incident.timeline.append(
                TimelineEvent(
                    timestamp=time.time(),
                    kind="escalated",
                    message=f"Escalated to {severity}",
                    actor=actor,
                )
            )
