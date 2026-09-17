# REALITY — Architecture (v0)

## 1. The one rule

> **Believed world state changes only through observations. Actions never
> directly mutate belief.**

Everything else is commentary. The simulator keeps *ground truth* (what is
actually true) strictly separate from the *believed world* (what the AI
thinks). The executor mutates ground truth. The observation source reads
ground truth and emits observations. The world learns only by ingesting
observations. That separation is what makes "the executor reported success
but the world was observed unchanged" a detectable, first-class event
rather than a philosophical puzzle.

## 2. Components

```
                    ┌─────────────────────────────────────┐
                    │            REALITY WORLD             │
                    │  (believed state — the AI's model)   │
                    │                                      │
  ┌──────────┐      │  spatial: zones, entities, adjacency  │
  │ OBSERVA- │─────▶│  state: per-entity attributes        │─────┐
  │ TION     │ apply │  provenance: per-attribute source/  │     │ query
  │ SOURCES  │      │    confidence/observation id        │     ▼
  └──────────┘      │  relationships, constraints,        │  ┌────────┐
                    │  capabilities, events (append-only) │  │ ask()  │
  ┌──────────┐      │  actions (lifecycle records)        │  │ JSON / │
  │ ACTION   │◀────▶│                                      │  │ human  │
  │ EXECUTOR │ exec │  ┌──────────────┐                   │  └────────┘
  └──────────┘      │  │ ACTION ENGINE │                   │
     (ground        │  │ propose →     │                   │
      truth)        │  │ authorize →   │                   │
                    │  │ execute →     │                   │
                    │  │ observe →     │                   │
                    │  │ verify        │                   │
                    │  └──────────────┘                   │
                    └─────────────────────────────────────┘
```

### `reality/core/models.py` — the vocabulary

- `Point`, `Zone`, `Entity`, `SpatialWorld` — the spatial substrate
  (pre-existing pipeline, kept dependency-free).
- `Entity.state` — mutable attributes (`status`, `availability`,
  `assignee`, `reserved_by`, …). `zone_id`/position are attributes too,
  normalized through the same path.
- `Provenance` — per-attribute `{observed_at, source, confidence,
  observation_id}`. Every belief carries its evidence pointer.
- `Observation` — `{id, ts, source, entity_id, observed_state,
  confidence, context}`. A claim about the world from a source, with a
  confidence the layer is allowed to doubt.
- `Event` — append-only `{id, ts, type, entity_id, details, caused_by,
  actor}`. The audit trail: observations recorded, state changes,
  conflicts, every action transition.
- `Action` — `{id, type, actor, target, parameters, status,
  authorization, expected_effect, executor_report, verification,
  rejection_reason, provenance, …timestamps}`. The full lifecycle in one
  record.
- `Relationship` — typed edges (`inside`, `assigned_to`, `member_of`,
  `operates_in`, …).
- `Constraint` — `{id, name, kind, applies_to, check, parameters,
  message}`. Checks are registered functions; **unknown checks fail
  closed** (reject).

Five deliberately small action types: `move_entity`, `reserve_resource`,
`change_status`, `assign_entity`, `notify`.

### `reality/core/world.py` — `RealityWorld`

Owns the spatial world plus relationships, observations, events, actions,
constraints, capabilities, and a baseline snapshot. Responsibilities:

- `apply_observation(obs)` — the **only** writer of believed state.
  Emits `observation_recorded` always; `state_changed` when a credible
  reading moves a value; `observation_for_unknown_entity` when the
  subject doesn't exist; `observation_conflict` when a weak reading
  contradicts a strong belief (the reading is kept on record, the belief
  is *not* overwritten — fail-safe on evidence quality).
- `history(entity_id)` / `state_at(entity_id, ts)` / `what_changed(since)`
  / `evidence_for(entity_id, attr)` — temporal and evidential queries.
- `validate()` — referential integrity (relationships, constraint
  targets, action targets).
- JSON `to_dict`/`from_dict` — the whole world, including history, is
  serializable.

### `reality/core/actions.py` — `ActionEngine`

The lifecycle:

```
proposed → authorized → executing → executed → observed → verified
                 ↘ rejected          ↘ failed      ↘ partially_verified
                                                 ↘ unknown
```

- `propose()` — validates the action type, enforces **capabilities**
  (a world declares which kinds offer which actions; anything else is
  refused), computes `expected_effect`, logs `action_proposed`.
- `authorize()` — evaluates constraints. Hard failures → `rejected`
  (with `rejection_reason`). Missing human approval → stays `proposed`
  ("awaiting approval") — a distinct, honest state, not a silent queue.
- `execute()` — calls the executor, records `executor_report`
  verbatim. The executor's claim is data, not truth.
- `ingest_observations()` — polls the observer, applies observations
  (belief updates happen *here*, never in `execute`), logs
  `action_observed`.
- `verify()` — compares `expected_effect` against believed state:
  `verified` / `partially_verified` / `failed` / `unknown` (executed but
  never observed — the layer admits what it doesn't know).
- `run()` — the full loop in one call. `available_actions()` —
  capability introspection for agents.

### `reality/core/verification.py`

Pure comparison of expected vs. observed. Each checked attribute records
its evidence observation id; the result exposes `evidence_ids` so any
verdict is auditable back to the readings it rested on.

### `reality/core/constraints.py`

Registry of check functions (`entity_exists`, `zone_exists`,
`zone_boundary_forbidden`, `resource_available`, `approval_required`,
`capability_allowed`, …). Constraints are data in the world file, so
policies (safety boundaries, approval gates) are inspectable and
versioned alongside the world — not buried in code.

### `reality/core/queries.py` — `ask_world()`

The AI-native interface. Structured JSON in, structured JSON out:

- State: "what is the status of p17", "why is p18 reserved"
- Time: "what changed", "history of p17"
- Evidence: "what evidence supports p17 being in storage-b?"
- Capability: "what actions can i take on p17"
- Action: "move p17 to storage-b" (plans without a runtime; executes
  the full lifecycle with one — approval declared via `approved_by`)
- Verification: "verify act-1", "did act-1 succeed"
- Composition: "find available workstation near finance team and
  prepare it for rosario" (spatial search → constraint pre-check →
  multi-action execution)

Falls back to the spatial `ask()` for pure geometry questions.
`--format human` renders the same answers as prose at the CLI.

### `reality/infra/adapters.py`

Three abstract seams — the entire future integration surface:

- `ObservationSource.poll(world) -> list[Observation]` — cameras, GPS,
  IoT, humans, external event feeds.
- `ActionExecutor.execute(action) -> {success, message}` — robots,
  enterprise APIs, human task dispatch.
- `WorldStateStore` — persistence backends (v0: JSON file).

### `reality/infra/simulation.py`

The first adapter pair, and deliberately the *only* environment v0
knows: a deterministic clock (fixed epoch), separate ground truth and
belief, a faithful executor/observer, and **fault injection**
(`report_success_without_effect`, `wrong_effect`, observation spoofing).
Deterministic ids and timestamps make every run reproducible — the
test suite asserts exact event equality across runs.

### `reality/infra/demo.py` — `reality demo`

The executable thesis narrative: observe → reason → propose (blocked
without approval) → approve → execute → observe → **verified**; then the
failure case: executor claims success, observation contradicts,
verification reports **failed** with an explicit discrepancy, and the
belief correctly stays where the camera says it is.

## 3. Data flow of one verified action

```
agent: "move p17 to storage-b" (approved_by=rosario)
  → propose:    Action(act-7, move_entity, p17→storage-b, proposed)
                + event action_proposed, expected_effect {zone_id: storage-b}
  → authorize:  constraints evaluated (boundary ok, approval present)
                → authorized + event
  → execute:    executor moves p17 in GROUND TRUTH, reports success
                → executed + event (report stored verbatim)
  → observe:    camera polls ground truth → Observation(obs-…,
                {zone_id: storage-b}, conf 0.95)
                → applied to BELIEF + events
  → verify:     expected storage-b vs believed storage-b → verified
                + event, evidence_ids → [obs-…]
```

If the executor lies (fault), the observe step reports storage-a, and
verify returns `failed` with `discrepancy: p17.zone_id: expected
'storage-b', observed 'storage-a' (via sim-camera-1 @ obs-…)`. The
action record then permanently shows `executor_report.success: true`
next to `verification.status: failed` — the distinction the thesis is
about, preserved as data.

## 4. What is intentionally absent

- No MIND (planner, learner, LLM). `ask()` matches patterns; it does
  not plan.
- No network, no cloud, no vector DB, no blockchain, no API keys.
- No real sensor/robot integrations — only the adapter interfaces.
- Concurrency is single-threaded; persistence is a JSON file.
- Geometry is 2D, pure-Python, dependency-free scaffolding
  (see thesis §4: spatial querying is a solved commodity, not the claim).
