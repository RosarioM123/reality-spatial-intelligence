# Adjacent Technology Survey — REALITY Thesis (Phase 2)

Date: 2026-09-17. Purpose: challenge the REALITY thesis before building.
Method: web research (docs, papers, project READMEs) on each adjacent
technology; for each, what it already provides and what it specifically does
NOT provide relative to the REALITY claim.

The REALITY claim under test: AI needs a structured action/state layer for
the external world — PERCEIVE → REPRESENT → REASON → PLAN → ACT → VERIFY —
with entities carrying state, relationships, provenance-stamped observations,
an explicit action lifecycle (proposed → authorized → executed → observed →
verified), constraints/authorization as first-class gates, and a verification
layer that distinguishes "the system reported success" from "I independently
observed the change."

---

## 1. Spatial databases (PostGIS, DuckDB-spatial, SedonaDB)

### Provides
- The best commoditized spatial query engine in existence: geometry/geography
  types, GiST/SP-GiST spatial indexes, hundreds of battle-tested functions
  (ST_Distance, ST_Contains, ST_Within, KNN, routing via pgRouting, raster,
  topology, linear referencing).
- Transactional integrity (ACID), mature multi-user story, SQL as a
  declarative query interface any agent can already speak.
- PostGIS is explicitly the "de facto GIS in SQL" for transactional
  workloads; DuckDB-spatial/SedonaDB cover embedded/analytical cases.

### Does NOT provide
- No notion of entity *state* beyond geometry: nothing about availability,
  status, ownership, or condition. A row is current truth; history requires
  bolting on audit tables.
- No time model (valid-time vs transaction-time must be hand-rolled).
- No actions, no action lifecycle, no authorization gates, no provenance or
  confidence on values.
- No observation concept: there is no distinction between "measured",
  "reported", and "inferred" — a value is a value.
- No verification semantics and no AI-native interface (SQL is agent-usable
  but not agent-designed: no capability discovery, no structured action
  contracts).

**Verdict:** the spatial-query *substrate* is a solved commodity. REALITY's v0
reimplements a weak subset of PostGIS in pure Python (point-in-polygon,
distance, BFS routing). That is fine for a dependency-free prototype, but the
thesis must not rest on spatial querying — that battle is lost and should
eventually be delegated (e.g., a PostGIS-backed `WorldStateStore` adapter).

## 2. GIS systems (QGIS, ArcGIS)

### Provides
- Cartography, geoprocessing workflows, spatial analysis, and data
  management tooling for human analysts; rich desktop/server ecosystems;
  OGC standards (WFS/WMS) for interoperability.

### Does NOT provide
- Everything in §1's "does not provide" list, plus: GIS is human-workflow
  software. There is no machine-actionable world state, no agent-facing
  action API, no real-time observation ingestion story, and no concept of
  acting *in* the world — only of analyzing representations of it.

**Verdict:** no overlap with the thesis beyond "deals with space." Not a
competitor; not a foundation.

## 3. Digital twins (Azure Digital Twins + DTDL)

### Provides
- The closest *conceptual* neighbor: a live twin graph of entities
  (twins) connected by typed relationships, modeled in DTDL (Digital Twins
  Definition Language) with properties, components, and relationships.
- Event-driven updates: telemetry ingress (IoT Hub → Function → twin
  property update), change notifications, and event routes to downstream
  endpoints (Event Grid/Hubs) for reactions.
- Data-plane RBAC and managed identity — real authorization primitives,
  though at the infrastructure layer, not the action layer.

### Does NOT provide — and this is damning for the "twins already do it" claim
- **DTDL defines Commands, but Azure Digital Twins does not support them.**
  There is no action-execution model at all: a twin is a *mirror*, and the
  platform explicitly refuses to close the loop back into the world.
- Telemetry is not stored; there is no built-in history — you must route to
  Time Series Insights / Data Explorer downstream and correlate yourself.
- No action lifecycle, no authorization *of actions* (only of API callers),
  no verification layer, no observation-vs-claim distinction: a property
  update is accepted as truth on write.
- No provenance/confidence model on state; no AI-native interface (queries
  are a SQL-like twin-graph language for humans/services, not an
  agent-action contract).

**Verdict:** digital twins validate the *problem* (a structured live model of
the world is valuable) while conceding the *thesis*: the leading commercial
twin platform deliberately stops at representation and leaves
act-and-verify to the customer. REALITY's claimed territory — the closed
perceive→act→verify loop — is exactly the hole twins don't fill. (Caveat:
Microsoft has been de-emphasizing ADT; the industrial-twin center of gravity
is moving to OpenUSD/Omniverse-style composition, covered in §6.)

## 4. Robotics middleware (ROS 2)

### Provides
- The most serious "already does this" candidate on the *action* side: ROS 2
  **actions** are goal/feedback/result/cancel message triples for
  long-running work (Nav2's `navigate_to_pose` is the canonical example) —
  a genuine action lifecycle primitive with unique goal IDs and
  preempt/cancel semantics.
- Lifecycle (managed) nodes with explicit state machines
  (unconfigured → inactive → active → finalized) for deterministic
  bringup/teardown.
- Topics/services/parameters, a huge driver ecosystem, and Nav2 behavior
  trees that already do plan → execute → monitor → recover.

### Does NOT provide
- **No canonical world state.** ROS is a message bus, not a state store:
  "where is package P17 and why do we believe that" has no first-class
  answer; every node keeps its own fragment. (rosbridge + a database is the
  usual hand-rolled fix — i.e., the thing REALITY proposes to be.)
- No provenance or confidence on state; no observation model (a topic
  message is trusted on arrival).
- No authorization layer: any node can publish a goal to any action server.
  No human-approval gates, no permission model over actions.
- No verification abstraction: nothing compares an action's *claimed*
  result against *independent* observation as a designed layer; recovery
  behaviors check task progress, not epistemic discrepancy.
- Robot-centric and operationally heavy: it models *a robot's* I/O, not a
  general environment (office, warehouse, campus) as an AI action domain.

**Verdict:** ROS 2 owns the *execution* half of the loop for robots and its
action primitive is genuinely close to REALITY's action concept. What it
lacks is everything around the action: canonical state, provenance,
authorization, and verification. "ROS 2 + a database" is the strongest
engineering alternative — but note it is an *architecture* nobody has
productized as an AI-facing layer, and wiring it up is exactly the
integration tax REALITY claims to eliminate.

## 5. Robot simulators (Gazebo, Isaac Sim, MuJoCo, PyBullet, CARLA)

### Provides
- Physics (rigid/deformable/cloth/fluid in Isaac Sim's PhysX; ODE/Bullet/
  DART in Gazebo), sensor simulation (cameras, LiDAR, IMU, force), and ROS
  bridges so the same nodes run against sim and hardware.
- Isaac Sim adds photorealistic RTX rendering, synthetic-data pipelines,
  and USD-native scenes — the current gold standard for sim-to-real
  perception training. Gazebo is the lightweight open-source workhorse.

### Does NOT provide
- No state *semantics*: a simulator computes the next physics step; it does
  not maintain "package P17 is reserved by Rosario, observed by camera-3
  with confidence 0.8."
- No actions as a typed, authorized, lifecycle-tracked abstraction — only
  actuator commands and topic messages.
- No history/provenance query layer ("what changed, why do we believe
  it"), no constraints, no AI-native interface beyond raw APIs.
- They simulate the world; they do not *represent it for reasoning*.

**Verdict:** simulators are *environments*, REALITY is a *layer above*
environments. The v0 plan already reflects this correctly: the simulator is
the first `ActionExecutor`/`ObservationSource` adapter, not the product.
No conflict; strong complementarity (a future REALITY could drive Isaac Sim
scenes as its "physical" backend).

## 6. Scene representations (OpenUSD; 3D dynamic scene graphs — Kimera/Hydra)

### Provides
- **OpenUSD**: the industry composition standard (Pixar, now AOUSD/Linux
  Foundation, eyeing ISO). Prims in a hierarchy, attributes vs.
  relationships, composition arcs (references, sublayers, payloads, variant
  sets) that merge multi-source scene descriptions without destructive
  edits, plus time-sampled data. Isaac Sim/Omniverse scenes *are* USD
  stages. This is the best existing answer to "one composable
  representation of a 3D environment from many authors."
- **3D dynamic scene graphs** (Armeni et al.; Kimera; Hydra): a *layered*
  graph — metric-semantic mesh → objects → places → rooms → buildings —
  with spatiotemporal edges, built in real time from visual-inertial/LiDAR
  data. Explicitly designed as a robot's "mental model" for hierarchical
  planning ("bring me the cup from the dining room table"). The closest
  existing art to REALITY's PERCEIVE → REPRESENT half.

### Does NOT provide
- USD is a *scene description*, not a world-state system: no live state
  semantics, no actions, no authorization, no verification, no provenance
  of belief. Composition arcs resolve *authoring* conflicts, not
  observation-vs-reality conflicts.
- DSGs are perception outputs: they answer "what is where" from sensors,
  not "what may I do," "what did I attempt," or "did it work." No action
  lifecycle, no constraints, no event/state history as a queryable
  epistemic record.
- Neither is AI-action-native: both are consumed by planners/renderers,
  not by language-model agents through a structured action contract.

**Verdict:** DSGs + USD are the right *representation lineage* for
REALITY's REPRESENT layer — a future REALITY should probably speak USD
and ingest DSG-style graphs. But representation is not the thesis; the
thesis starts where these stop: acting and verifying.

## 7. World models (ML: Dreamer, JEPA/V-JEPA 2, Genie, Sora)

### Provides
- Learned predictive dynamics: Dreamer-style latent dynamics models that
  roll out imagined trajectories for planning; V-JEPA 2-AC which predicts
  *representations* (not pixels) conditioned on actions and plans with CEM
  in latent space — demonstrated on real robot manipulation tasks.
- The "imagine futures, pick actions" loop is a genuine perceive→predict→
  plan substrate, and 2026 has seen massive investment ($3.2B per Dealroom
  estimates cited by WEF) on the bet that this is the path to physical AI.

### Does NOT provide
- **Latent, not inspectable:** a world model cannot answer "why is the
  machine marked unavailable" or "what evidence supports P17's location."
  There is no symbolic state, no queryable history, no provenance.
- No authorization, no constraints, no action lifecycle states — a policy
  outputs torques/tokens, not auditable authorized actions.
- Prediction is not verification: a world model predicts what *should*
  happen; it has no machinery for detecting that the world *disagreed*
  with the prediction, let alone attributing the discrepancy.
- Data-hungry and hardware-gated (Stanford HAI's warning: interaction data
  concentrates among fleet owners).

**Verdict:** world models are the *MIND-side* bet on dynamics, and the
user's own architecture places them in MIND, not REALITY. They are a
possible future *consumer* of REALITY's verified state transitions (as
training signal: proposed → observed → verified triples are exactly the
action-consequence data world models are starved of). No overlap at the
layer REALITY claims.

## 8. MCP and agent tool-use frameworks (LangChain, AutoGen, ReAct)

### Provides
- **MCP** (Model Context Protocol): the emerging standard interface between
  models and the world — *tools* (executable functions with JSON schemas),
  *resources* (read-only context), *prompts* (workflow templates) over
  JSON-RPC, with OAuth 2.1-aligned auth and user-consent semantics. It is
  winning the interface war: one server, many models.
- **LangChain/AutoGen/CrewAI**: ReAct-style reason→act→observe loops,
  multi-agent orchestration, human-in-the-loop hooks. The "agent" side of
  acting in the world is well explored.

### Does NOT provide
- MCP tools are **stateless function calls**: `move_package({id, zone})`
  returns a result and forgets. There is no world model behind the tools,
  no lifecycle across calls, no memory of what was attempted vs. observed,
  no verification that the effect persisted.
- No authorization *model* — only transport auth and per-call consent. No
  constraint checking against world state ("is this action permitted given
  current state?") as a designed layer.
- Agent frameworks orchestrate *cognition*; they treat the environment as
  an opaque tool boundary. The ReAct "observation" is whatever text the
  tool returned — which is precisely the conflation REALITY wants to
  eliminate (tool said success ≠ world changed).
- A 2025 Trail of Bits audit found 68% of enterprise agent deployments
  pass tool output to the LLM unsanitized — the ecosystem's epistemic
  hygiene is poor, which is REALITY's opening, not its refutation.

**Verdict:** MCP is not a competitor; it is REALITY's most likely
*distribution interface*. The correct end-state is probably "REALITY as an
MCP server": tools backed by a stateful world with lifecycle, auth, and
verification, instead of stateless functions. Agent frameworks are the
demand side. Nothing here provides the supply side.

## 9. Temporal / event-sourced databases (Datomic, SirixDB, event sourcing)

### Provides
- Exactly the history substrate REALITY's v0 needs: append-only event
  logs as the source of truth, materialized current-state projections,
  and **bitemporal** modeling — *valid time* (when true in the world) vs.
  *transaction time* (when recorded) — which is precisely the machinery for
  "where was X, where is it now, why do we believe it changed."
- Datomic (fact-level, built-in time) and SirixDB (embeddable, bitemporal,
  structural sharing) show this is productizable, not just a pattern.
- Notably, agent-infrastructure projects are independently converging here
  (e.g., an AI-agent decision-trace ADR choosing event-sourced bitemporal
  modeling for auditability and replay).

### Does NOT provide
- Storage is not semantics: these systems record *whatever you write*
  with no model of actions, observations, constraints, or verification.
  They will faithfully store both the lie ("move succeeded") and the
  truth ("camera still shows P17 in Zone A") without noticing the conflict.
- No spatial/embodied model, no AI-action interface, no authorization
  workflow.

**Verdict:** adopt, don't compete. REALITY's event/state history should be
bitemporal event-sourced storage (even in-memory/JSON for v0, with the
valid-time/transaction-time distinction explicit). This is the least
controversial borrow in the whole survey.

## 10. Home Assistant (state machine + services + event bus)

### Provides
- The closest thing to REALITY that already runs in millions of homes: a
  central **state machine** (entity_id → state string + attributes +
  last_changed/last_updated), an **event bus** (`state_changed` and friends),
  a **service registry** (literally renamed "actions" in the UI), area/device/
  entity registries, recorder history, and YAML automations
  (trigger → condition → action).
- Real observation ingestion from heterogeneous sources (sensors, APIs,
  humans) with `unavailable`/`unknown` as first-class epistemic states —
  a genuine precedent for "the system knows what it doesn't know."

### Does NOT provide
- No action *lifecycle*: calling a service is fire-and-forget. There is no
  proposed → authorized → executed → observed → verified; no record linking
  an action to its observed outcome.
- No verification layer and no discrepancy detection as designed
  machinery (the community builds it ad hoc per automation; one
  third-party project even had to add an "OutcomeTracker: act→verify
  loop" as an *external* engine — evidence the core lacks it).
- No authorization model over actions beyond "who can call the API";
  no constraint checking against world state before execution.
- No provenance/confidence on state values; history records *what* the
  state was, not *why the system believed it*.
- Device-centric, not world-centric: it models controllable devices, not
  a general environment of entities, relationships, and spatial structure
  that an AI reasons over.

**Verdict:** the most dangerous "already exists" objection after the
simulation one, because HA is real, deployed, and open-source. But its
center of gravity is home automation for humans, and its architecture
treats action outcomes as trusted. REALITY's bet is that the missing
pieces — lifecycle, authorization, verification, provenance — are not
patches but the actual product. Honest note: if those pieces turn out to
be easily bolted onto HA as an integration, the thesis shrinks to a
feature.

## 11. Embodied-AI benchmarks (Habitat, Habitat 3.0)

### Provides
- Habitat-Sim: thousands of fps photorealistic simulation; Habitat-Lab: a
  modular task/benchmark API (PointGoal, ObjectGoal, Rearrangement
  pick-and-place, social navigation with humanoids in 3.0) that
  standardized embodied-AI evaluation. The gym-style
  `reset() → step(action) → obs/reward/done` loop is the field's shared
  action-observation contract.

### Does NOT provide
- Episodic, not persistent: no world state survives across episodes; no
  long-lived entities with history.
- Rewards are task scores, not a general action/verification
  infrastructure. The environment *is* the ground truth — there is no
  observation-vs-reality gap *by construction*, so verification is
  meaningless inside it.
- No authorization, no constraints beyond physics, no provenance, no
  AI-native state-query interface.

**Verdict:** benchmarks measure agents; REALITY is infrastructure agents
would use. Habitat is a plausible *test harness* for REALITY (adversarial
observation injection in sim is exactly how you'd test verification
without hardware), not a competitor.

---

## Strongest objections, ranked by damage

### Objection 1 — "Without real hardware, the verification claim is theatrical." (MOST DAMAGING)
**Steelman:** The thesis's centerpiece — distinguishing "reported success"
from "independently observed change" — cannot be genuinely demonstrated in
a simulation where the same codebase both executes actions and generates
observations. The v0 failure case ("action reports success but observation
contradicts it") is *scripted*: the demo author injects the contradiction.
A scripted discrepancy proves the comparison code runs, not that the
abstraction discovers anything. No investor, roboticist, or skeptic should
update their beliefs based on it.
**Honest assessment:** this lands. It doesn't kill the thesis, but it
demotes the v0 from "demonstration" to "executable specification." The
mitigation is to make the simulation *adversarial rather than scripted*:
separate the executor and observer into genuinely independent processes
with a fault-injection harness neither side knows about, and score
detection rates over randomized fault campaigns. Even better: the honest
v0 claim is "here is the *interface* and *semantics* of verification" —
like a type system, valuable before any program runs. But the burden of
proof for "this catches real discrepancies" requires either hardware or a
simulator the team does not control (e.g., run the observer against
Habitat/Isaac Sim as a black box). **Thesis survives, narrowed:** v0 proves
the abstraction; it does not prove the value.

### Objection 2 — "This is a CRUD app over a database with extra steps."
**Steelman:** proposed → authorized → executed → observed → verified is a
five-state state machine any competent engineer builds in an afternoon.
Append-only event log? Event sourcing 101. Provenance? Audit columns.
Constraints? A policy check before the write. There is no deep technical
moat here — it's enterprise workflow software with robotics vocabulary.
**Honest assessment:** half-true and the most important objection for
scoping. The *mechanisms* are indeed unoriginal; if the thesis were "we
invented a new kind of state machine," it would be dead. What is not
commoditized is the *packaging as an AI-facing contract*: no existing
system gives an LLM agent, through one interface, a queryable world with
typed actions, authorization gates, provenance-stamped observations, and
verification semantics. The moat — if any — is ecosystem and developer
experience (like MCP's: JSON-RPC was not novel either), not algorithms.
The thesis must therefore be framed as infrastructure/standardization
play, never as algorithmic novelty. **Thesis survives reframed; dies as a
research claim.**

### Objection 3 — "Home Assistant already exists."
**Steelman:** millions of installations maintain entity state, ingest
heterogeneous observations, expose actions ("services"), keep history, and
run automations against a live world model. The delta REALITY proposes —
lifecycle states, auth gates, verification — is a plugin, not a platform.
**Honest assessment:** the strongest *existence proof* against novelty,
and the reason the v0 must pick domains HA doesn't serve (warehouse,
campus, factory — multi-actor, spatially rich, beyond device control).
HA's device-centrism and trusted-outcome architecture are real gaps, but
they are bridgeable gaps. If the team cannot articulate why REALITY isn't
"HA with an OutcomeTracker and an approval queue," the thesis is a
feature. The differentiator has to be demonstrated, not asserted — the
warehouse demo must do things HA's model *cannot express* (e.g.,
contradictory observations with confidence-weighted belief revision;
authorization policies evaluated against world state). **Thesis survives
only if the demo proves inexpressibility in HA terms.**

### Objection 4 — "ROS 2 + a database already does this."
**Steelman:** ROS 2 actions already have goal/feedback/result/cancel with
unique IDs; add Postgres and you have state + history; add a verification
node comparing commanded vs. observed topics and you have discrepancy
detection. Robotics teams ship this shape routinely.
**Honest assessment:** true as an *architecture*, false as a *product*.
Nobody has packaged "ROS 2 + a database + verification + auth" as a
reusable AI-facing layer; every team hand-rolls it, which is precisely the
integration tax REALITY claims to remove. Also ROS 2 is robot-centric and
operationally heavy, while REALITY targets any environment an AI might act
in. The objection usefully constrains the thesis: REALITY must be *simpler
to adopt than standing up ROS 2* and must work where ROS 2 doesn't go
(offices, enterprise APIs, human-in-the-loop workflows). **Thesis survives
as a productization play.**

### Objection 5 — "Verification is just polling a sensor."
**Steelman:** industry has done expected-vs-actual comparison for decades —
SCADA alarming, thermostat closed loops, Nav2's "am I making progress"
monitors. Dressing it up as "epistemic verification" is marketing.
**Honest assessment:** the *comparison* is old; what's new is making the
*distinction between claim and observation* a first-class, queryable,
provenance-tracked part of the agent's world model. A thermostat doesn't
maintain "the controller claims 22°C, the independent sensor reads 19°C,
confidence 0.7, last verified 40s ago, action #418 disputed" as state an
AI can reason over. SCADA alarms to humans; REALITY is supposed to inform
*agents*. Fair compromise: the v0 should acknowledge the lineage
("closed-loop control, made legible to AI") rather than claim invention.
**Thesis survives with honest framing.**

### Objection 6 — "Digital twins already do this."
**Steelman:** Azure Digital Twins, Omniverse-based industrial twins —
billion-dollar investments in live world models with relationships,
telemetry, and event routing.
**Honest assessment:** the weakest of the serious objections, because the
twin platforms explicitly stop at representation: ADT doesn't support
commands at all, and industrial twins are visualization/monitoring
systems. They validate the problem and vacate the solution space.
**Thesis survives comfortably** — but should plan to *integrate* with
twin representations (USD/DTDL import as an adapter) rather than compete.

### Objection 7 — "The spatial parts are a solved commodity."
**Steelman:** PostGIS does everything v0's geometry does, better, with
indexes. The Point → Zone → Entity model is a weak GIS.
**Honest assessment:** conceded outright. Spatial querying must never be
the thesis; it's scaffolding. The v0's pure-Python geometry is justified
only as dependency-free prototyping, and the roadmap should name
PostGIS (or equivalent) as the future `WorldStateStore`. Any thesis draft
that leans on "we can answer what's near what" is leaning on nothing.
**Thesis survives by excluding spatial querying from its claims.**

---

## Implications for docs/thesis.md

1. **Narrow the claim.** REALITY is not a database, not a simulator, not a
   robot middleware, not a world model. It is an *AI-facing contract for
   acting in the world with epistemic hygiene*: typed world state +
   authorized actions with lifecycles + provenance-stamped observations +
   verification of claimed vs. observed effects.
2. **State the falsifiers explicitly** (the user asked what would falsify
   the thesis):
   - If, in a randomized adversarial simulation campaign, an agent using
     REALITY's lifecycle detects no more discrepancies and takes no fewer
     unsafe actions than an agent using raw stateless tools (MCP-style)
     plus a careful prompt, the lifecycle adds no measurable value.
   - If the v0's verification, once built, is obviously reducible to "a
     checklist any team would write anyway" with no emergent benefit from
     the unified model, the thesis is a feature, not a layer.
   - If Home Assistant (or ADT + Functions, or ROS 2 + Postgres) can
     express the warehouse demo's full semantics — contradictory
     observations, confidence-weighted belief, state-dependent
     authorization, disputed actions — without contortion, build there
     instead.
3. **Borrow aggressively:** bitemporal event-sourced history (§9), MCP as
   the future agent interface (§8), USD/DSG as representation lineage
   (§6), Habitat/Isaac Sim as adversarial test harnesses (§11, §5).
4. **Do not compete** with PostGIS (§1/§7-objection), ROS 2 execution
   (§4), or learned world models (§7) — adapter to all three.
5. **The v0's honest job** is to be an executable specification of the
   semantics (Objection 1): prove the *abstraction* is coherent and
   expressive, not that it catches real-world discrepancies. Say so in
   the docs.
