"""Tests for incident management."""

import pytest

from reality.core.incidents import (
    INCIDENT_ACKNOWLEDGED,
    INCIDENT_OPEN,
    INCIDENT_RESOLVED,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SOURCE_MANUAL,
    SOURCE_TELEMETRY,
    IncidentManager,
)


def test_raise_and_lifecycle():
    mgr = IncidentManager()
    inc = mgr.raise_incident("Robot dark", robot_id="r1", source=SOURCE_TELEMETRY)
    assert inc.status == INCIDENT_OPEN
    assert inc.severity == SEVERITY_WARNING
    assert len(inc.timeline) == 1
    assert inc.timeline[0].kind == "created"

    mgr.acknowledge(inc.id, actor="ops", note="Looking into it")
    assert mgr.incidents[inc.id].status == INCIDENT_ACKNOWLEDGED

    mgr.add_note(inc.id, "Found it near the depot", actor="ops")
    assert len(mgr.incidents[inc.id].timeline) == 3

    mgr.resolve(inc.id, actor="ops", note="Robot recovered")
    resolved = mgr.incidents[inc.id]
    assert resolved.status == INCIDENT_RESOLVED
    assert resolved.resolved_at is not None


def test_dedup_returns_existing():
    mgr = IncidentManager()
    first = mgr.raise_incident(
        "Robot dark", robot_id="r1", source=SOURCE_TELEMETRY, dedup_key="r1-dark"
    )
    second = mgr.raise_incident(
        "Robot still dark",
        robot_id="r1",
        source=SOURCE_TELEMETRY,
        dedup_key="r1-dark",
    )
    assert first.id == second.id
    assert len(mgr.incidents) == 1


def test_dedup_escalates_severity():
    mgr = IncidentManager()
    inc = mgr.raise_incident(
        "Robot stale",
        robot_id="r1",
        severity=SEVERITY_WARNING,
        dedup_key="r1-dark",
    )
    escalated = mgr.raise_incident(
        "Robot lost",
        robot_id="r1",
        severity=SEVERITY_CRITICAL,
        dedup_key="r1-dark",
    )
    assert escalated.id == inc.id
    assert escalated.severity == SEVERITY_CRITICAL
    assert any(e.kind == "escalated" for e in escalated.timeline)


def test_dedup_ignores_resolved():
    mgr = IncidentManager()
    inc = mgr.raise_incident("Robot dark", robot_id="r1", dedup_key="r1-dark")
    mgr.resolve(inc.id, actor="ops")
    new = mgr.raise_incident("Robot dark again", robot_id="r1", dedup_key="r1-dark")
    assert new.id != inc.id


def test_resolve_twice_rejected():
    mgr = IncidentManager()
    inc = mgr.raise_incident("Test", source=SOURCE_MANUAL)
    mgr.resolve(inc.id, actor="ops")
    with pytest.raises(ValueError, match="already resolved"):
        mgr.resolve(inc.id, actor="ops")


def test_acknowledge_resolved_rejected():
    mgr = IncidentManager()
    inc = mgr.raise_incident("Test", source=SOURCE_MANUAL)
    mgr.resolve(inc.id, actor="ops")
    with pytest.raises(ValueError, match="already resolved"):
        mgr.acknowledge(inc.id, actor="ops")


def test_unknown_incident():
    mgr = IncidentManager()
    with pytest.raises(KeyError):
        mgr.acknowledge("inc-nope", actor="ops")


def test_open_incidents_and_summary():
    mgr = IncidentManager()
    mgr.raise_incident("A", robot_id="r1", severity=SEVERITY_CRITICAL)
    mgr.raise_incident("B", robot_id="r2", severity=SEVERITY_INFO)
    done = mgr.raise_incident("C", robot_id="r1")
    mgr.resolve(done.id, actor="ops")

    assert len(mgr.open_incidents()) == 2
    summary = mgr.summary()
    assert summary["total"] == 3
    assert summary["open"] == 2
    assert summary["by_severity"][SEVERITY_CRITICAL] == 1


def test_for_robot():
    mgr = IncidentManager()
    mgr.raise_incident("A", robot_id="r1")
    mgr.raise_incident("B", robot_id="r2")
    mgr.raise_incident("C", robot_id="r1")
    assert len(mgr.for_robot("r1")) == 2
    assert len(mgr.for_robot("r3")) == 0


def test_incident_to_dict():
    mgr = IncidentManager()
    inc = mgr.raise_incident("Robot dark", robot_id="r1", source=SOURCE_TELEMETRY)
    d = inc.to_dict()
    assert d["robot_id"] == "r1"
    assert d["source"] == SOURCE_TELEMETRY
    assert d["status"] == INCIDENT_OPEN
    assert len(d["timeline"]) == 1
