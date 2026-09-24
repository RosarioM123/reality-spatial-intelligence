"""Telemetry and heartbeat monitoring for robots in the field.

The core field-operations problem: machines leave the depot, go remote,
and sometimes go dark. This module tracks heartbeats from every robot,
detects stale/missing robots, and surfaces fleet-wide health — the
minimum viable "are my machines okay?" layer.

Design notes:
- Heartbeats are observations, not state writes. A heartbeat *reports*
  battery/position/status; the world's believed state updates only if
  the report passes validation (same rule as everything else here).
- Staleness is computed, not stored. `stale_robots()` derives it from
  last-seen timestamps against a configurable threshold.
- Alert levels: OK -> DEGRADED (stale) -> CRITICAL (missing too long)
  -> LOST (beyond recovery window).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# Alert levels, in escalating severity.
ALERT_OK = "ok"
ALERT_DEGRADED = "degraded"  # heartbeat stale, within grace period
ALERT_CRITICAL = "critical"  # missing beyond grace period
ALERT_LOST = "lost"  # missing beyond recovery window


@dataclass
class Heartbeat:
    """One telemetry report from a robot."""

    robot_id: str
    timestamp: float
    battery: float | None = None
    position: tuple[float, float] | None = None
    zone_id: str | None = None
    status: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "robot_id": self.robot_id,
            "timestamp": self.timestamp,
            "battery": self.battery,
            "position": list(self.position) if self.position else None,
            "zone_id": self.zone_id,
            "status": self.status,
            "extra": self.extra,
        }


@dataclass
class RobotHealth:
    """Computed health snapshot for one robot."""

    robot_id: str
    alert: str
    seconds_since_heartbeat: float | None
    last_battery: float | None
    last_zone: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "robot_id": self.robot_id,
            "alert": self.alert,
            "seconds_since_heartbeat": self.seconds_since_heartbeat,
            "last_battery": self.last_battery,
            "last_zone": self.last_zone,
        }


class TelemetryMonitor:
    """Tracks heartbeats and computes fleet health.

    stale_after: seconds without a heartbeat before DEGRADED.
    critical_after: seconds before CRITICAL.
    lost_after: seconds before LOST.
    """

    def __init__(
        self,
        stale_after: float = 30.0,
        critical_after: float = 120.0,
        lost_after: float = 600.0,
    ):
        if not (0 < stale_after < critical_after < lost_after):
            raise ValueError("thresholds must satisfy 0 < stale < critical < lost")
        self.stale_after = stale_after
        self.critical_after = critical_after
        self.lost_after = lost_after
        self._heartbeats: dict[str, Heartbeat] = {}
        self._history: dict[str, list[Heartbeat]] = {}

    # -- ingestion --------------------------------------------------------

    def ingest(self, heartbeat: Heartbeat) -> None:
        """Record a heartbeat. Out-of-order beats are kept in history
        but do not move the last-seen pointer backwards."""
        history = self._history.setdefault(heartbeat.robot_id, [])
        history.append(heartbeat)
        current = self._heartbeats.get(heartbeat.robot_id)
        if current is None or heartbeat.timestamp >= current.timestamp:
            self._heartbeats[heartbeat.robot_id] = heartbeat

    def ingest_many(self, heartbeats: list[Heartbeat]) -> None:
        for hb in heartbeats:
            self.ingest(hb)

    # -- queries -----------------------------------------------------------

    def last_heartbeat(self, robot_id: str) -> Heartbeat | None:
        return self._heartbeats.get(robot_id)

    def history(self, robot_id: str, limit: int = 100) -> list[Heartbeat]:
        return self._history.get(robot_id, [])[-limit:]

    def health(self, robot_id: str, now: float | None = None) -> RobotHealth:
        """Health of one robot. Unknown robots report as LOST."""
        now = time.time() if now is None else now
        hb = self._heartbeats.get(robot_id)
        if hb is None:
            return RobotHealth(
                robot_id=robot_id,
                alert=ALERT_LOST,
                seconds_since_heartbeat=None,
                last_battery=None,
                last_zone=None,
            )
        age = now - hb.timestamp
        if age >= self.lost_after:
            alert = ALERT_LOST
        elif age >= self.critical_after:
            alert = ALERT_CRITICAL
        elif age >= self.stale_after:
            alert = ALERT_DEGRADED
        else:
            alert = ALERT_OK
        return RobotHealth(
            robot_id=robot_id,
            alert=alert,
            seconds_since_heartbeat=age,
            last_battery=hb.battery,
            last_zone=hb.zone_id,
        )

    def fleet_health(
        self, robot_ids: list[str], now: float | None = None
    ) -> dict[str, Any]:
        """Fleet-wide health rollup."""
        now = time.time() if now is None else now
        health = [self.health(rid, now=now) for rid in robot_ids]
        by_alert: dict[str, int] = {}
        for h in health:
            by_alert[h.alert] = by_alert.get(h.alert, 0) + 1
        needs_attention = [h.robot_id for h in health if h.alert != ALERT_OK]
        return {
            "total": len(health),
            "by_alert": by_alert,
            "needs_attention": needs_attention,
            "robots": [h.to_dict() for h in health],
        }

    def stale_robots(self, robot_ids: list[str], now: float | None = None) -> list[str]:
        """Robots that haven't reported within the stale threshold."""
        now = time.time() if now is None else now
        return [
            rid
            for rid in robot_ids
            if (hb := self._heartbeats.get(rid)) is None
            or (now - hb.timestamp) >= self.stale_after
        ]
