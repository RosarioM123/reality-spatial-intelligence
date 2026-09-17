# REALITY — Roadmap

**Status convention:** only V0 exists. V1–V3 are plans, not promises —
nothing below implies future features exist. Each version is gated by a
question the previous version cannot answer.

---

## V0 — Executable specification (THIS REPO, DONE)

*Question: is the abstraction coherent and expressive?*

- Believed state writable only via observations; ground-truth/belief
  split in simulation.
- Entity state + per-attribute provenance; relationships; constraints;
  capabilities.
- Action lifecycle: proposed → authorized → executed → observed →
  verified (plus rejected / failed / partially_verified / unknown).
- Constraint-gated authorization with human approval as a distinct state.
- Verification comparing expected effect vs. observed belief, with
  evidence ids on every verdict.
- Append-only event log; temporal queries (`history`, `state_at`,
  `what_changed`); evidential queries (`evidence_for`).
- Plain-language `ask()` over state, history, evidence, capabilities,
  plans, actions, verification.
- Deterministic simulator with fault injection
  (`report_success_without_effect`, `wrong_effect`, observation
  spoofing); warehouse + office example worlds.
- Adapter interfaces defined: `ObservationSource`, `ActionExecutor`,
  `WorldStateStore`.
- 93 tests, including the full
  observation → state → plan → action → event → observation →
  verification loop and the executor-lie failure case.
- Docs: thesis (with objections and falsifiers), architecture,
  design decisions, this roadmap.

*Honest limit:* the failure case is scripted. V0 proves the semantics
are coherent — it does not prove they catch real discrepancies.

## V1 — Adversarial validation (NOT STARTED)

*Question: does the lifecycle add measurable value over stateless tools?*

This is the version that can kill the thesis. Falsifiers are in
`docs/thesis.md` §6.

- **Randomized fault-injection campaigns**: separate the executor and
  observer into genuinely independent processes; neither knows the
  fault schedule. Score discrepancy-detection rates over hundreds of
  randomized runs.
- **Baseline comparison**: an agent using REALITY's lifecycle vs. an
  agent using raw stateless tools (MCP-style) + a careful prompt, on
  the same fault campaigns. Metrics: discrepancies detected, unsafe
  actions taken, false alarms.
- **Black-box environment**: run the observer against a simulator the
  team does not control (Habitat / Isaac Sim) to break the
  "same-codebase" circularity.
- Kill criteria: if the lifecycle shows no measurable advantage, the
  thesis is a feature, not a layer — say so and stop.

## V2 — One real environment (NOT STARTED)

*Question: does the abstraction survive contact with real sensors and
actuators?*

- Exactly one physical or high-fidelity environment (a real room with
  cameras, or a warehouse aisle — not five).
- One real `ObservationSource` (e.g., camera → detector → observations
  with honest confidence) and one real `ActionExecutor` (e.g., a mobile
  base, a warehouse API, or human task dispatch with confirmation).
- Latency, partial observability, and sensor dropout handled as
  first-class `unknown`/conflict states — not as exceptions.
- Persistence beyond JSON (bitemporal event store; PostGIS-backed
  `WorldStateStore` for the spatial substrate).
- MCP server packaging: REALITY as tools backed by stateful world
  state, so any MCP-compatible agent can use it.

## V3 — Toward the full loop (NOT STARTED)

*Question: can WORLD → MIND → REALITY → WORLD run as a system?*

- MIND remains a separate project; V3 defines the contract it must
  speak (typed actions, capability discovery, evidence queries) and the
  outcome feed it consumes (verified transition triples as training
  signal for learned world models).
- Multi-actor authorization (roles, delegation, audit).
- USD/DTDL import adapters (representation lineage, not competition).
- Long-horizon history with bitemporal queries (valid time vs.
  transaction time) as a designed layer, not an afterthought.

---

## Explicit non-goals (all versions)

No generic chatbot, no vector DB, no blockchain, no cloud dependency
for the core, no fake-AI pattern matching presented as reasoning, no
claim that spatial querying is novel (delegate to PostGIS when the
scaffolding stops being enough).
