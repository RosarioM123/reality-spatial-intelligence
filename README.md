# REALITY — the action/state layer for AI in the physical world

**Thesis:** AI systems that act in the physical world need a dedicated
layer that keeps *what was attempted*, *what was reported*, and *what was
independently observed* rigorously separate — and verifies the first
against the third.

This repository is **v0: an executable specification** of that layer's
semantics, built simulation-first. It proves the abstraction is coherent
and expressive. It does *not* prove it catches real-world discrepancies —
that requires hardware or an uncontrolled simulator (see
[docs/thesis.md](docs/thesis.md) §5, objection 1, and the falsifiers in
§6). The docs are blunt about what exists and what doesn't; start there
if you're evaluating the idea rather than the code.

Part of a three-layer picture: **WORLD** (state of work) → **MIND**
(cognition) → **REALITY** (state/action interface to the environment) →
WORLD. MIND is not implemented here. This repo is REALITY only.

## The loop

```
PERCEIVE → REPRESENT → REASON ABOUT → PLAN → ACT UPON → VERIFY
```

The central distinction, as working machinery:

| Stage | Example |
|---|---|
| Proposed action | `move_entity(p17 → storage-b)` submitted |
| Authorized action | constraints pass; human approval recorded |
| Executor-reported success | "moved P17 to Storage B" (a *claim*) |
| Independently observed outcome | camera: P17 still in Storage A, conf 0.95 (*evidence*) |
| Verified result | `failed` — with the discrepancy spelled out |

One rule governs everything: **believed world state changes only
through observations. Actions never directly mutate belief.** The
simulator keeps *ground truth* strictly separate from the AI's *believed
world*, so "the executor lied" is a detectable event, not a paradox.

## Install

Requires Python 3.10+. No third-party dependencies.

```bash
git clone https://github.com/RosarioM123/reality-spatial-intelligence.git
cd reality-spatial-intelligence
pip install -e .
```

## Quickstart

```bash
# The executable thesis: a warehouse run with a success AND a caught lie
reality demo

# Plain-language reasoning over a simulated world (JSON answers)
reality ask examples/warehouse.json "where is package p17?" --format human
reality ask examples/warehouse.json "what changed" --format human
reality ask examples/warehouse.json "what evidence supports p17 being in storage-a?" --format human

# Action questions run the full lifecycle (approval declared explicitly)
reality ask examples/warehouse.json "move p17 to storage-b" --approve-as rosario --format human

# Composition: spatial search -> constraint check -> multi-action execution
reality ask examples/office.json \
  "find available workstation near finance team and prepare it for rosario" --format human

# Direct action/state commands
reality state examples/warehouse.json p17        # believed state + provenance
reality history examples/warehouse.json p17      # state transitions over time
reality act examples/warehouse.json move_entity p17 \
  --param to_zone=storage-b --actor cli --approve-as rosario
reality verify-action examples/warehouse.json act-1

# Spatial primitives (the pre-existing pipeline, kept as substrate)
reality validate examples/office.json
reality route examples/office.json office-a office-b
reality near examples/office.json 5 4 10 --kind equipment
reality zones examples/office.json
```

Or from Python:

```python
import json
from reality.infra.simulation import Simulation
from reality.core.queries import ask_world

sim = Simulation(json.load(open("examples/warehouse.json")))
sim.observe()  # beliefs are born from observations

print(ask_world(sim.world, "where is package p17?")["entity"]["zone_id"])
# storage-a

action = sim.act("move_entity", "agent-1", "p17", {"to_zone": "storage-b"},
                 approved_by="rosario")
print(action.status, action.verification["status"])
# verified verified

# The failure case: executor claims success, observation disagrees
bad = sim.engine.propose("move_entity", "agent-1", "p17", {"to_zone": "packing"})
sim.add_fault(bad.id, "report_success_without_effect")
sim.engine.authorize(bad, approved_by="rosario")
sim.engine.execute(bad)          # reports success (it lies)
sim.engine.ingest_observations(bad)
print(sim.engine.verify(bad).status)   # failed
print(sim.engine.verify(bad).discrepancies)
# ["p17.zone_id: expected 'packing', observed 'storage-a' (via sim-camera-1 @ obs-…)"]
```

## World file format (v0)

A world is a JSON document: spatial substrate plus the action/state
model.

```json
{
  "zones": [{"id": "storage-a", "name": "Storage A", "floor": 0,
             "polygon": [[0,0],[10,0],[10,8],[0,8]]}],
  "entities": [{"id": "p17", "name": "Package P17", "kind": "package",
                "position": [3,4], "zone_id": "storage-a",
                "state": {"status": "intake", "availability": "available"}}],
  "adjacency": {"storage-a": ["packing"], "packing": ["storage-a"]},
  "relationships": [{"from": "p17", "type": "stored_in", "to": "storage-a"}],
  "capabilities": {"package": ["move_entity", "change_status", "notify"]},
  "constraints": [{"id": "c-move-approval", "name": "moves need approval",
                   "kind": "approval", "applies_to": ["move_entity"],
                   "check": "approval_required"}]
}
```

- `state`: mutable attributes; every attribute carries provenance
  (source, confidence, observation id) once observed.
- `capabilities`: which entity kinds offer which actions — enforced at
  proposal time.
- `constraints`: policies as data (safety boundaries, resource limits,
  human approval). Unknown checks fail closed.

See `examples/warehouse.json` (full action/verification scenario) and
`examples/office.json` (spatial + workstation scenario).

## Project structure

```
reality/
  config.py            # settings (env-overridable: REALITY_*)
  core/
    models.py          # entities, state, provenance, observations,
                       # events, actions, relationships, constraints
    world.py           # RealityWorld: beliefs, history, evidence, validation
    actions.py         # ActionEngine: propose→authorize→execute→
                       #   observe→verify
    constraints.py     # check registry (fail-closed)
    verification.py    # expected-vs-observed comparison
    queries.py         # ask_world(): plain-language AI-native interface
    geometry.py        # dependency-free 2D geometry (scaffolding)
    pipeline.py        # spatial ingest → validate → index → query
  infra/
    adapters.py        # ObservationSource / ActionExecutor / WorldStateStore
    simulation.py      # deterministic simulator + fault injection
    demo.py            # `reality demo`: the end-to-end narrative
    store.py           # JSON persistence
    cli.py             # `reality` command-line interface
  docs/
    thesis.md          # the claim, narrowed; objections; falsifiers
    architecture.md    # components and the data flow of one action
    roadmap.md         # V0 (done) / V1 / V2 / V3 (plans, not promises)
    design-decisions.md# why the core choices were made
  research/
    adjacent-tech.md   # honest survey: PostGIS, twins, ROS 2, HA, MCP, …
examples/              # warehouse.json, office.json
tests/                 # pytest suite (93 tests)
```

### Earlier prototype modules

Four modules from a May-2026 prototype are preserved as-is for
reference and are **not** part of the working system or test suite:
`reality/core/edge_processor.py`, `reality/core/scene_graph.py`,
`reality/infra/telemetry_server.py`, `reality/infra/transport.py`.
They expect undeclared heavy dependencies (`opencv-python`, `numpy`,
`flask`, `psutil`). See `docs/design-decisions.md` §10.

## Configuration

Optional environment variables: `REALITY_DATA_DIR`,
`REALITY_DEFAULT_RADIUS`, `REALITY_MAX_RESULTS`.

## Tests

```bash
pytest                    # 93 tests, ~0.2s, no network, no randomness
```

## Limitations (honest)

- Simulation-first: the discrepancy demo is scripted fault injection.
  It validates the *semantics*, not real-world detection.
- No hardware, network, cloud, ML, vector DB, or blockchain. No API
  keys or secrets anywhere.
- `ask()` is pattern matching over structured state, not a planner —
  it is the interface a future MIND would reason against, not MIND
  itself.
- Single-threaded; JSON-file persistence; 2D dependency-free geometry
  is scaffolding (spatial querying is a solved commodity — delegate to
  PostGIS when it matters).
- Action lifecycle states are strings, not a formal state machine
  library — deliberately, to keep the prototype legible.

## Further reading

- [docs/thesis.md](docs/thesis.md) — the narrowed claim, the seven
  objections, what would falsify it
- [docs/architecture.md](docs/architecture.md) — components and one
  action's full data flow
- [docs/roadmap.md](docs/roadmap.md) — V0 done; V1 is designed to be
  able to kill the thesis
- [docs/design-decisions.md](docs/design-decisions.md) — the durable
  choices and their costs
