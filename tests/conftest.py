"""Shared fixtures for the REALITY v0 test suite."""

import json
import os

import pytest

from reality.infra.simulation import Simulation

HERE = os.path.dirname(__file__)


def _load(name):
    with open(os.path.join(HERE, "..", "examples", name),
              encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def warehouse_data():
    return _load("warehouse.json")


@pytest.fixture
def office_data():
    return _load("office.json")


@pytest.fixture
def sim(warehouse_data):
    return Simulation(warehouse_data)


@pytest.fixture
def observed_sim(sim):
    sim.observe()
    return sim
