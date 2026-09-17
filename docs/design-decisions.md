# REALITY — Design Decisions

Durable decisions and the reasoning behind them. Newest last.

## 1. Belief changes only through observations

*Decision:* `RealityWorld.apply_observation` is the sole writer of
believed state. `ActionEngine.execute` mutates nothing the AI believes;
it only records the executor's report.

*Why:* the entire thesis collapses if actions write belief directly —
then "verified" would mean "we did what we said," which is circular.
The ground-truth/belief split in the simulator exists to make this
enforced by construction, not by convention.

*Cost:* every action needs an observation round before verification,
which is slower and more awkward than trusting the executor. That
awkwardness is the product.

## 2. Weak contradictory evidence does not overwrite strong belief

*Decision:* if a new observation contradicts current belief with
substantially lower confidence (`new + 0.3 < old`), the layer logs
`observation_conflict`, keeps the reading on record, and does **not**
update the belief or its provenance.

*Why:* a low-confidence camera glitch (or a spoofed sensor) should not
silently rewrite what the system believes. The conflict event is the
signal; something upstream (a human, a better sensor, MIND) resolves it.
Fail-safe on evidence quality.

*Alternative rejected:* "latest observation always wins" — simpler, but
lets weak evidence vandalize strong belief with no trace in the belief
itself (only in the event log).

## 3. Unknown checks fail closed

*Decision:* a constraint referencing an unregistered check function
rejects the action.

*Why:* an action layer that silently permits what it cannot evaluate is
unsafe by default. Fail-closed is the only defensible posture for a
system whose job is gating physical consequences.

## 4. Capabilities are declared by the world, enforced by the engine

*Decision:* each world file declares `capabilities: {kind: [actions]}`;
`propose()` refuses actions not offered for the target's kind
(`ValueError`, fail fast).

*Why:* "what can be done to what" is world knowledge, not engine
knowledge. A package is not assignable; a dock door is not movable.
Putting it in the world file keeps the engine generic and the policy
inspectable.

## 5. Approval is a state, not a queue

*Decision:* an action needing human approval that lacks it stays
`proposed` with the engine reporting "awaiting approval" — distinct
from `rejected`.

*Why:* conflating "not yet allowed" with "forbidden" loses information
the agent needs ("ask Rosario" vs. "don't do that"). The lifecycle
keeps all six distinctions from the thesis legible as data.

## 6. Verification admits ignorance

*Decision:* `verify()` returns `unknown` when an action was executed
but never observed, rather than assuming success or failure.

*Why:* the layer's credibility depends on saying "I don't know" when
the evidence isn't there. An `unknown` action is a prompt to go look —
which is exactly the behavior the thesis wants to cultivate.

## 7. Deterministic simulation, fixed epoch

*Decision:* the simulator's clock starts at a fixed epoch, ids are
counters, there is no randomness. Tests assert exact event equality
across runs.

*Why:* a prototype whose demo is not reproducible is a story, not a
specification. Determinism also makes fault-injection campaigns (V1)
meaningful: same seed, same faults, comparable results.

## 8. Standard library only, no over-engineering

*Decision:* zero third-party dependencies; ~2.5k lines; five action
types; JSON files.

*Why:* the user instruction was explicit — optimize for discovering
whether REALITY is a real technical abstraction, not for looking
impressive. Every dependency is a claim that the abstraction needs it;
v0 needs none. (The May-2026 prototype modules that want
OpenCV/Flask/NumPy are preserved untouched and excluded from the
working system — see §10.)

## 9. The v0 is an executable specification, not a validation

*Decision:* document plainly that the failure demo is scripted and
proves the abstraction, not the value (thesis §5, objection 1).

*Why:* claiming more than the evidence supports would poison the
project's epistemics — and this is a project *about* epistemics. The
roadmap's V1 is designed to be capable of killing the thesis.

## 10. Earlier prototype modules stay isolated

*Decision:* `reality/core/edge_processor.py`,
`reality/core/scene_graph.py`, `reality/infra/telemetry_server.py`,
`reality/infra/transport.py` (May 2026) are preserved as-is, documented
in the README as non-working reference, and excluded from tests and
imports.

*Why:* they expect undeclared heavy dependencies and reference modules
that don't exist in this tree. Fixing them would add exactly the
dependency weight v0 refuses (§8), and their concerns (frame
processing, telemetry transport) belong to future *adapters*, not the
core model. Revisit if/when a real `ObservationSource` needs them.

## 11. Ask is an interface, not a mind

*Decision:* `ask_world()` is pattern matching over structured state —
no LLM, no planner. Action questions execute only with an attached
runtime, and approval-gated actions execute only with a declared
`approved_by`.

*Why:* the moment the interface pretends to reason, the prototype
starts faking AI. Its job is to be the *target* that a future MIND
reasons against: structured, queryable, honest about what it doesn't
know. (MIND is a separate, unbuilt layer by design.)
