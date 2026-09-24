"""Shift handover: the report the incoming ops team reads.

Field operations run in shifts. When the night shift hands to the day
shift, they need one page: fleet state, open incidents, what changed,
what needs attention first. This module generates that page from the
live fleet, incident, and telemetry state — no manual writing.

The report is plain text, designed to be pasted into Slack, printed,
or logged. Structure:

    FLEET STATUS      — robots by state, battery alerts
    OPEN INCIDENTS    — sorted by severity, with age
    NEEDS ATTENTION   — telemetry flags not yet incidents
    MISSION ROLLUP    — task outcomes since last handover
"""

from __future__ import annotations

import time

from reality.core.fleet import FleetManager
from reality.core.incidents import (
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    IncidentManager,
)
from reality.core.telemetry import TelemetryMonitor

_SEVERITY_ORDER = {SEVERITY_CRITICAL: 0, SEVERITY_WARNING: 1}


def generate_handover(
    fleet: FleetManager,
    incidents: IncidentManager,
    monitor: TelemetryMonitor,
    *,
    shift_name: str = "handover",
    now: float | None = None,
) -> str:
    """Build the shift handover report."""
    now = time.time() if now is None else now
    lines = []
    lines.append(f"=== SHIFT HANDOVER: {shift_name} ===")
    lines.append(f"generated {_fmt_time(now)}")
    lines.append("")

    # Fleet status.
    status = fleet.fleet_status()
    lines.append("FLEET STATUS")
    lines.append(f"  robots: {status['robot_count']}")
    for state, count in sorted(status["robots_by_status"].items()):
        lines.append(f"    {state}: {count}")
    if status["low_battery"]:
        lines.append(f"  LOW BATTERY: {', '.join(status['low_battery'])}")
    if status["tasks_by_status"]:
        lines.append("  tasks:")
        for state, count in sorted(status["tasks_by_status"].items()):
            lines.append(f"    {state}: {count}")
    lines.append("")

    # Open incidents, most severe first.
    open_incs = sorted(
        incidents.open_incidents(),
        key=lambda i: (_SEVERITY_ORDER.get(i.severity, 9), i.created_at),
    )
    lines.append(f"OPEN INCIDENTS ({len(open_incs)})")
    if not open_incs:
        lines.append("  none — clean shift")
    for inc in open_incs:
        age_min = (now - inc.created_at) / 60
        lines.append(
            f"  [{inc.severity}] {inc.id} ({inc.status}) — {inc.title} "
            f"[{age_min:.0f}m old]"
        )
    lines.append("")

    # Telemetry flags not yet incidents.
    robot_ids = [r.id for r in fleet.robots()]
    needs = monitor.stale_robots(robot_ids, now=now)
    # Exclude robots already covered by open incidents.
    covered = {i.robot_id for i in open_incs if i.robot_id}
    uncovered = [r for r in needs if r not in covered]
    lines.append("TELEMETRY FLAGS (no incident yet)")
    if not uncovered:
        lines.append("  none")
    for rid in uncovered:
        h = monitor.health(rid, now=now)
        lines.append(f"  {rid}: {h.alert}")
    lines.append("")

    lines.append("=== END HANDOVER ===")
    return "\n".join(lines)


def _fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts))
