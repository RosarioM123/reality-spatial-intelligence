"""End-to-end tests: the complete
observation -> state -> plan -> action -> event -> observation ->
verification loop, in simulation."""


def test_full_e2e_loop_success(observed_sim):
    sim = observed_sim
    world = sim.world
    # 1. observation -> state
    assert world.get_attribute("p17", "zone_id") == "storage-a"
    # 2. plan + action: full lifecycle
    action = sim.act(
        "move_entity",
        "ai-agent",
        "p17",
        {"to_zone": "storage-b"},
        approved_by="rosario",
        provenance="e2e",
    )
    # 3. events were emitted for every transition
    types = {e.type for e in world.events}
    for expected in (
        "observation_recorded",
        "state_changed",
        "action_proposed",
        "action_authorized",
        "action_executed",
        "action_observed",
        "action_verified",
    ):
        assert expected in types
    # 4. verified result
    assert action.status == "verified"
    assert world.get_attribute("p17", "zone_id") == "storage-b"
    # 5. evidence chain closes: provenance -> observation record
    ev = world.evidence_for("p17", "zone_id")
    assert ev["evidence"]["observation_id"] == action.verification["evidence_ids"][0]


def test_e2e_executor_lie_detected(observed_sim):
    """The distinguishing case: executor-reported success vs observed
    outcome. Belief must follow the observation, and verification must
    report failure with an explicit discrepancy."""
    sim = observed_sim
    world = sim.world
    engine = sim.engine
    action = engine.propose(
        "move_entity", "ai-agent", "p17", {"to_zone": "packing"}, provenance="e2e"
    )
    sim.add_fault(action.id, "report_success_without_effect")
    engine.authorize(action, approved_by="rosario")
    ok, _ = engine.execute(action)
    assert ok is True
    assert action.executor_report["success"] is True  # reported success
    engine.ingest_observations(action)
    result = engine.verify(action)
    assert result.status == "failed"  # observed outcome
    assert action.status == "failed"
    # Belief follows observation, not the executor's report.
    assert world.get_attribute("p17", "zone_id") == "storage-a"
    # The lie is on the record: the executor's report and the observed
    # outcome disagree, and the verification says so explicitly.
    reported = next(
        e
        for e in world.events
        if e.type == "action_executed" and e.caused_by.get("id") == action.id
    )
    assert reported.details["report"]["success"] is True
    assert action.verification["discrepancies"] != []
    assert "packing" in action.verification["discrepancies"][0]


def test_e2e_wrong_effect_detected(observed_sim):
    sim = observed_sim
    engine = sim.engine
    action = engine.propose(
        "move_entity", "ai-agent", "p17", {"to_zone": "packing"}, provenance="e2e"
    )
    sim.add_fault(action.id, "wrong_effect", to_zone="office")
    engine.authorize(action, approved_by="rosario")
    engine.execute(action)
    engine.ingest_observations(action)
    result = engine.verify(action)
    assert result.status == "failed"
    assert "packing" in result.discrepancies[0]


def test_simulation_is_deterministic(warehouse_data):
    from reality.infra.simulation import Simulation

    s1 = Simulation(warehouse_data)
    s2 = Simulation(warehouse_data)
    a1 = s1.act("change_status", "t", "dock-door-1", {"status": "open"})
    a2 = s2.act("change_status", "t", "dock-door-1", {"status": "open"})
    assert a1.id == a2.id
    assert a1.verified_at == a2.verified_at
    assert s1.world.events[0].id == s2.world.events[0].id
    assert [e.to_dict() for e in s1.world.events] == [
        e.to_dict() for e in s2.world.events
    ]


def test_rejected_action_leaves_no_belief_change(observed_sim):
    sim = observed_sim
    world = sim.world
    n_events = len(world.events)
    action = sim.engine.run(
        "move_entity", "t", "p17", {"to_zone": "office"}, approved_by="rosario"
    )
    assert action.status == "rejected"
    assert world.get_attribute("p17", "zone_id") == "storage-a"
    # The rejection itself is recorded; the world is not.
    rejected = [e for e in world.events[n_events:] if e.type == "action_rejected"]
    assert len(rejected) == 1
