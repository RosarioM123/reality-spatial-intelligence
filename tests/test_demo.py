"""Tests for the end-to-end demo (reality/infra/demo.py)."""

import os

from reality.infra.cli import main
from reality.infra.demo import run_demo

HERE = os.path.dirname(__file__)
WAREHOUSE = os.path.join(HERE, "..", "examples", "warehouse.json")


def test_run_demo_returns_zero_and_completes(capsys):
    assert run_demo(WAREHOUSE) == 0
    out = capsys.readouterr().out
    assert "Demo complete" in out


def test_run_demo_catches_executor_lie(capsys):
    run_demo(WAREHOUSE)
    out = capsys.readouterr().out
    assert "FAILURE CASE" in out
    assert "discrepancy" in out


def test_run_demo_tracks_package_p17(capsys):
    run_demo(WAREHOUSE)
    out = capsys.readouterr().out
    assert "p17" in out
    assert "verified" in out


def test_cli_demo_subcommand(capsys):
    assert main(["demo", WAREHOUSE]) == 0
    out = capsys.readouterr().out
    assert "Demo complete" in out
