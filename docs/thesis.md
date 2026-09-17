# REALITY — Thesis

**Claim:** AI systems that act in the physical world need a dedicated
*action/state layer* — a structured, queryable model of the environment
that maintains the distinction between *what was attempted*, *what was
reported*, and *what was independently observed*.

This repository is a simulation-first prototype (v0) of that layer. It is
an **executable specification of the semantics**, not a demonstration that
the semantics catch real-world discrepancies. That distinction matters and
is defended in [§5](#5-the-strongest-objections).

---

## 1. The three layers

| Layer   | Role | Question it answers |
|---------|------|---------------------|
| WORLD   | State of work | What is being done, by whom, what is its status? |
| MIND    | Cognition | What should be done, and why? (planning, judgment, learning) |
| REALITY | State/action interface to the environment | What is true out there, what can be done, did it work? |

The intended future flow is **WORLD → MIND → REALITY → WORLD**: work
intentions become cognition, cognition becomes grounded action through
REALITY, and observed outcomes flow back into WORLD as state. MIND is
explicitly **not implemented** in this repository. WORLD is a separate
project. This repo is REALITY only.

## 2. The loop

```
PERCEIVE → REPRESENT → REASON ABOUT → PLAN → ACT UPON → VERIFY
```

Every stage exists in ordinary robotics and automation. The thesis is not
that the loop is novel — it is that **no existing system gives an AI
agent all six stages through one coherent, inspectable interface**, and
that the missing piece is specifically the right-hand side: the disciplined
separation of *attempt* from *outcome*.

## 3. The central distinction

An agent acting in the world must be able to distinguish six things that
today's tool-calling stacks routinely conflate:

1. **Planned action** — what the agent intends ("move package P17 to
   Storage B").
2. **Requested/proposed action** — the typed, parameterized action
   submitted to the layer (`move_entity(p17 → storage-b)`).
3. **Authorized action** — the action after constraints and approvals
   pass. A proposed action that fails a safety constraint is *rejected*;
   one that needs a human is *proposed, awaiting approval* — never
   silently executed, never silently dropped.
4. **Executor-reported success** — what the thing that ran the action
   *claims* happened ("moved P17 to Storage B").
5. **Independently observed outcome** — what perception sources report
   afterwards (camera: P17 still in Storage A, confidence 0.95).
6. **Verified result** — the layer's judgment comparing 2's expected
   effect against 5: `verified`, `partially_verified`, `failed`, or
   `unknown` (executed but never observed).

Items 4 and 5 are the whole game. A tool that returns "success" is a
*claim*. A camera frame is *evidence*. An agent that cannot tell them
apart cannot be trusted with physical consequences, and today's dominant
agent pattern — stateless tool calls whose text output is trusted on
arrival — structurally cannot tell them apart.

## 4. What the thesis is NOT

Narrowing the claim is the point of the research in
`research/adjacent-tech.md`. REALITY is:

- **Not a database.** PostGIS/DuckDB-spatial own spatial querying;
  Datomic/SirixDB own bitemporal history. REALITY should eventually
  *use* these as storage, not compete with them.
- **Not a simulator.** Gazebo/Isaac Sim simulate physics; REALITY
  represents the world *for reasoning*. The simulator in this repo is
  the first `ActionExecutor`/`ObservationSource` adapter, not the product.
- **Not robot middleware.** ROS 2 owns execution for robots (its action
  primitive — goal/feedback/result — is genuinely close to ours). REALITY
  is the layer *around* execution: canonical state, provenance,
  authorization, verification — packaged for any environment, not just
  robots.
- **Not a world model.** Learned dynamics (Dreamer, JEPA) are MIND-side
  bets. They predict; they cannot answer "why do we believe P17 is
  there" or "who authorized this." Verified state transitions
  (proposed → observed → verified) are, however, exactly the
  action-consequence data those models are starved of — a future
  consumer relationship.
- **Not a digital twin.** Azure Digital Twins — the leading commercial
  twin platform — explicitly does not support DTDL Commands: a twin is a
  *mirror*, and the platform refuses to close the loop back into the
  world ([Microsoft Learn](https://learn.microsoft.com/lt-lt/azure/digital-twins/concepts-models):
  "DTDL for Azure Digital Twins must not define any commands").
  Twins validate the *problem* and vacate the *solution space*.
- **Not Home Assistant.** HA is the most dangerous "already exists"
  objection: real, deployed, with entity state, history, and "actions."
  But its architecture treats action outcomes as trusted — there is no
  lifecycle linking an action to its observed outcome, no verification
  layer, no authorization model over actions, no provenance on values.
  If those turn out to be easily bolted on, the thesis shrinks to a
  feature. The warehouse demo must do things HA's model cannot express.

What remains after all exclusions: **an AI-facing contract for acting in
the world with epistemic hygiene** — typed world state, authorized
actions with lifecycles, provenance-stamped observations, and
verification of claimed vs. observed effects. The moat, if any, is
ecosystem and developer experience (like MCP's — JSON-RPC was not novel
either), not algorithms. This is an infrastructure/standardization play,
never a research claim.

## 5. The strongest objections

Ranked by damage. Each is steelmanned; the thesis survives all of them
only in narrowed form.

**1. "Without real hardware, the verification claim is theatrical."**
(MOST DAMAGING.) In a simulation, the same codebase executes actions and
generates observations; the failure demo's discrepancy is *injected by
the demo author*. A scripted discrepancy proves the comparison code runs,
not that the abstraction discovers anything. **Concession:** the v0 is an
executable specification of verification semantics — like a type system,
valuable before any program runs. It proves the *abstraction* is coherent
and expressive, not that it catches real discrepancies. The burden of
proof for real value requires hardware or a simulator the team does not
control (e.g., observing a black-box Habitat/Isaac Sim scene).

**2. "This is a CRUD app with extra steps."** The lifecycle is a
five-state state machine; the event log is event sourcing 101;
constraints are policy checks. **Concession:** the mechanisms are
unoriginal. What is not commoditized is the *packaging as an AI-facing
contract*: no existing system gives an LLM agent, through one interface,
a queryable world with typed actions, authorization gates,
provenance-stamped observations, and verification semantics.

**3. "Home Assistant already exists."** See §4. The differentiator must
be demonstrated, not asserted.

**4. "ROS 2 + a database already does this."** True as an *architecture*,
false as a *product*. Nobody has packaged it as a reusable AI-facing
layer; every team hand-rolls it. REALITY must be simpler to adopt than
standing up ROS 2 and must work where ROS 2 doesn't go (offices,
enterprise APIs, human workflows).

**5. "Verification is just polling a sensor."** The *comparison* is old
(SCADA, thermostats, Nav2 monitors). What's new is making the
claim-vs-observation distinction first-class, queryable, and
provenance-tracked *for the agent's own reasoning* — "the controller
claims 22°C, the independent sensor reads 19°C, confidence 0.7, action
#418 disputed." Fair framing: "closed-loop control, made legible to AI."

**6. "Digital twins already do this."** The weakest objection — twins
stop at representation by design (see §4).

**7. "Spatial querying is a solved commodity."** Conceded outright. The
v0's pure-Python geometry is dependency-free scaffolding, never the
thesis.

## 6. What would falsify the thesis

An honest thesis states its falsifiers:

1. If, in a randomized adversarial simulation campaign, an agent using
   REALITY's lifecycle detects no more discrepancies and takes no fewer
   unsafe actions than an agent using raw stateless tools (MCP-style)
   plus a careful prompt, the lifecycle adds no measurable value.
2. If the v0's verification turns out to be obviously reducible to "a
   checklist any team would write anyway," with no emergent benefit from
   the unified model, the thesis is a feature, not a layer.
3. If Home Assistant (or ADT + Functions, or ROS 2 + Postgres) can express
   the warehouse demo's full semantics — contradictory observations,
   confidence-weighted belief, state-dependent authorization, disputed
   actions — without contortion, build there instead.

## 7. What v0 demonstrates, and what it does not

**Demonstrates:**
- The six-way distinction (§3) as working, tested machinery.
- Believed state that changes *only* through observations.
- Constraint-gated authorization with human approval.
- Discrepancy detection when executor claims and observations disagree.
- Plain-language reasoning over state, history, evidence, and actions.
- Adapter seams for real cameras, GPS, IoT, robots, maps, and
  enterprise APIs — defined, not implemented.

**Does not demonstrate:**
- That verification catches *real* discrepancies (see objection 1).
- Any hardware integration, any network service, any ML.
- MIND (cognition/planning) — the `ask()` interface reasons, but it is
  pattern matching over structured state, not a planner.
- Scale, multi-user concurrency, or persistence beyond JSON files.

The next experiment that would actually move the needle: an adversarial
fault-injection campaign (randomized, scored detection rates) against a
simulator the verification layer does not control.
