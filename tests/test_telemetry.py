"""Tests for telemetry and heartbeat monitoring."""

import pytest

from reality.core.telemetry import (
    ALERT_CRITICAL,
    ALERT_DEGRADED,
    ALERT_LOST,
    ALERT_OK,
    Heartbeat,
    TelemetryMonitor,
)


def _monitor() -> TelemetryMonitor:
    return TelemetryMonitor(stale_after=30.0, critical_after=120.0, lost_after=600.0)


def _hb(robot_id: str, ts: float, **kwargs) -> Heartbeat:
    return Heartbeat(robot_id=robot_id, timestamp=ts, **kwargs)


def test_healthy_robot():
    mon = _monitor()
    mon.ingest(_hb("r1", 1000.0, battery=90.0, zone_id="depot"))
    h = mon.health("r1", now=1010.0)
    assert h.alert == ALERT_OK
    assert h.seconds_since_heartbeat == 10.0
    assert h.last_battery == 90.0
    assert h.last_zone == "depot"


def test_degraded_after_stale_threshold():
    mon = _monitor()
    mon.ingest(_hb("r1", 1000.0))
    assert mon.health("r1", now=1031.0).alert == ALERT_DEGRADED
    assert mon.health("r1", now=1029.0).alert == ALERT_OK


def test_critical_after_critical_threshold():
    mon = _monitor()
    mon.ingest(_hb("r1", 1000.0))
    assert mon.health("r1", now=1121.0).alert == ALERT_CRITICAL


def test_lost_after_lost_threshold():
    mon = _monitor()
    mon.ingest(_hb("r1", 1000.0))
    assert mon.health("r1", now=1601.0).alert == ALERT_LOST


def test_unknown_robot_is_lost():
    mon = _monitor()
    h = mon.health("ghost", now=1000.0)
    assert h.alert == ALERT_LOST
    assert h.seconds_since_heartbeat is None


def test_out_of_order_heartbeat_does_not_regress():
    mon = _monitor()
    mon.ingest(_hb("r1", 1010.0, battery=80.0))
    mon.ingest(_hb("r1", 1005.0, battery=85.0))  # late arrival
    last = mon.last_heartbeat("r1")
    assert last is not None
    assert last.timestamp == 1010.0
    assert last.battery == 80.0
    # But it's in history.
    assert len(mon.history("r1")) == 2


def test_history_limit():
    mon = _monitor()
    for i in range(10):
        mon.ingest(_hb("r1", 1000.0 + i))
    assert len(mon.history("r1", limit=3)) == 3


def test_fleet_health_rollup():
    mon = _monitor()
    mon.ingest(_hb("r1", 1000.0, battery=90.0))
    mon.ingest(_hb("r2", 900.0, battery=50.0))  # stale at now=1000
    result = mon.fleet_health(["r1", "r2", "r3"], now=1000.0)
    assert result["total"] == 3
    assert result["by_alert"][ALERT_OK] == 1
    assert result["by_alert"][ALERT_DEGRADED] == 1
    assert result["by_alert"][ALERT_LOST] == 1
    assert set(result["needs_attention"]) == {"r2", "r3"}


def test_stale_robots():
    mon = _monitor()
    mon.ingest(_hb("r1", 1000.0))
    mon.ingest(_hb("r2", 900.0))
    stale = mon.stale_robots(["r1", "r2", "r3"], now=1000.0)
    assert set(stale) == {"r2", "r3"}


def test_invalid_thresholds_rejected():
    with pytest.raises(ValueError):
        TelemetryMonitor(stale_after=120.0, critical_after=30.0, lost_after=600.0)
    with pytest.raises(ValueError):
        TelemetryMonitor(stale_after=0.0, critical_after=30.0, lost_after=600.0)


def test_heartbeat_to_dict():
    hb = _hb("r1", 1000.0, battery=90.0, position=(5.0, 7.0), zone_id="depot")
    d = hb.to_dict()
    assert d["robot_id"] == "r1"
    assert d["position"] == [5.0, 7.0]
    assert d["zone_id"] == "depot"
