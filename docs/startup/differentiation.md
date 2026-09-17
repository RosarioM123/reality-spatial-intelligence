# REALITY — Differentiation Audit

**Date:** 2026-09-17 (startup program, Week 1 Thursday)
**Method:** component-by-component audit of the v0 codebase against the
adjacent-technology survey (`research/adjacent-tech.md`) and the narrowed
thesis (`docs/thesis.md`).

**Verdict up front:** no single mechanism in this repository is novel or
defensible as IP. What is unusual — and the only thing that could support
a company — is the *composition*: a typed, AI-facing contract that
enforces epistemic discipline (belief ← observations only) around action
in the physical world. Everything else is standard infrastructure wearing
a new hat. This document says which is which, and what would have to be
true for the differentiated part to become a moat.

---

## 1. Component verdicts

| Component | Verdict | Why |
|---|---|---|
| 2D spatial querying (point-in-polygon, distance, BFS zone routing) | **Commodity** | PostGIS/DuckDB-spatial do this better. Ours is dependency-free scaffolding, explicitly not the thesis. |
| Append-only event log | **Commodity** | Event sourcing 101. |
| Action lifecycle state machine (proposed → authorized → executed → observed → verified) | **Commodity as mechanism** | Temporal, Airflow, and ROS 2 actions (goal/feedback/result) all do lifecycle tracking. The *states* are standard; see §2 for what isn't. |
| Constraint checks, fail-closed | **Commodity** | Every policy engine does this. |
| Capability declarations per entity kind | **Commodity** | Basic typing / RBAC-shaped. |
| Per-attribute provenance (source, confidence, observation id) | **Commodity as mechanism** | Standard data lineage. The *use* of it (below) is less standard. |
| Temporal queries (`history`, `state_at`, `what_changed`) | **Commodity** | Bitemporal DBs (Datomic, SirixDB) do this properly; ours is a sketch. |
| JSON persistence, CLI, regex `ask()` | **Commodity** | Plumbing. |
| Deterministic simulator + fault injection | **Commodity as practice** | Good test hygiene, not a moat. (Valuable as a *harness* for V1, not as product.) |
| Six-way action distinction as queryable data (planned / proposed / authorized / executor-reported / observed / verified) | **Differentiated** | No surveyed system models all six *for an AI agent's reasoning*. ROS 2 tracks execution-side states; Home Assistant trusts execution; Azure Digital Twins refuses commands entirely. The gap is real but narrow. |
| Enforced epistemic rule: belief changes only via observations; ground-truth/belief split structural in the simulator | **Differentiated as discipline** | Unusual as an *architectural invariant*. But it is a discipline any careful team could adopt — not IP, not a technical barrier. Replicable in weeks. |
| Verification verdicts with evidence IDs, built for agent self-interrogation ("why do you believe P17 is there?" → observation ids + confidences) | **Differentiated** | Genuinely missing from MCP-style stateless tool calling, which is the dominant agent pattern. This is the sharpest edge of the v0. |
| MCP-shaped contract: typed actions, capability discovery, authorization gates, evidence queries — packaged for LLMs | **Differentiated as packaging** | The moat here is standardization and developer experience, like MCP itself (JSON-RPC was not novel either). Packaging moats are real but slow and require distribution. |

## 2. What is genuinely differentiated (defended)

Three things, in decreasing order of defensibility:

1. **The claim-vs-observation distinction as a data model.** Today an
   agent's tool returns "success" and the agent believes it. REALITY
   stores the executor's report and the independent observation as
   separate records and *compares* them. Nothing in the survey does
   this as an agent-facing primitive. This is the thesis's load-bearing
   wall.
2. **Evidence-addressable belief.** Every belief points to the
   observations (with confidences) that justify it, and contradictory
   low-confidence evidence is quarantined rather than applied. An agent
   can ask "what evidence supports this?" and "what contradicts it?" —
   the beginning of machine-checkable epistemics.
3. **The contract, not the code.** If this becomes anything, it becomes
   it the way MCP did: not through algorithms, but by being the
   simplest standard thing in the room. That requires integrations and
   distribution, not more v0 code.

## 3. What is merely standard infrastructure

Everything in the left column of the table marked **Commodity**:
geometry, event log, lifecycle mechanics, constraints, capabilities,
provenance mechanics, temporal queries, persistence, CLI, query parsing,
simulation harness. A competent team replicates the v0 in weeks — it is
~2,500 lines of standard-library Python. None of it is a barrier to
entry, and none of it should be presented as one.

## 4. What could become a real moat (all speculative)

- **Verified action-transition data as training fuel.** Every
  proposed → observed → verified triple is exactly the
  action-consequence data that learned world models (MIND-side) are
  starved of. If REALITY deployments generate this data at scale, the
  dataset — not the code — becomes the moat. Speculative; requires
  deployments first.
- **Ecosystem lock-in via the contract.** If "REALITY-shaped" tools
  become how agents act in warehouses/offices, switching costs accrue.
  Requires distribution and integrations (V2/V3), not v0 features.
- **One demonstrated discrepancy catch on real hardware.** A single
  documented case where the layer caught a real executor lie that would
  have caused physical/financial harm is worth more than the entire v0.
  This is the V1/V2 milestone that matters.

## 5. What would change this assessment

- If the V1 adversarial campaign shows the lifecycle adds no measurable
  value over stateless tools + careful prompting → the differentiated
  column collapses; honest outcome is "feature, not company" (a
  verification library for existing agent frameworks, or contributions
  to Home Assistant / ROS 2).
- If Home Assistant (or equivalent) gains claim-vs-observation
  verification natively → the packaging moat evaporates; build there.
- If a competitor ships the contract first with real integrations →
  we become a fast follower or an adapter, not the standard.

## 6. Startup implication

Compete on **integration breadth and developer experience**, never on
algorithms. Do not patent-chase the lifecycle; do chase the first real
deployment that produces verified-transition data. The next
highest-leverage work is not code — it is the V1 experiment that can
kill the thesis, and one concrete operational wedge (see the upcoming
Tuesday wedge-research mission) narrow enough to deploy against.
