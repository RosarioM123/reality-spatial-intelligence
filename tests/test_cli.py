"""Tests for the reality CLI (reality/infra/cli.py)."""

import json

import pytest

from reality import __version__
from reality.infra.cli import main


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert __version__ in out


def test_fleet_basic(capsys):
    rc = main(["fleet", "examples/fleet.json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "fleet: 4 robots" in out


def test_fleet_detail(capsys):
    rc = main(["fleet", "examples/fleet.json", "--detail"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "r-hauler-1" in out
    assert "battery" in out
    assert "caps" in out


def test_fleet_missing_file():
    with pytest.raises(SystemExit):
        main(["fleet", "examples/does-not-exist.json"])


def test_validate_ok(capsys):
    rc = main(["validate", "examples/fleet.json"])
    assert rc == 0


def test_validate_bad_file(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"not": "a world"}))
    with pytest.raises(SystemExit) as exc:
        main(["validate", str(bad)])
    assert exc.value.code == 1


def test_zones(capsys):
    rc = main(["zones", "examples/fleet.json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "depot" in out
