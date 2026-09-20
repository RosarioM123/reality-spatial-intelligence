# REALITY: Week 1 Founder and Technical Review

**Date:** 2026-09-20 · **Mission:** Day 3 of 10, startup validation program (BOTH day)
**Scope:** the v0 codebase, the differentiation audit (2026-09-17), Saturday's
wedge research (2026-09-19).
**Nature of this document:** a review, not new research. No new evidence was
gathered today; the judgments below are read off the existing record, and every
unsupported claim is marked as such.

---

## 1. Strongest evidence

**The thesis is executable, not a whitepaper.** The v0 (~2,500 lines of
standard-library Python, 124 tests passing (93 original + 31 added in the
09-18 upgrade), deterministic simulator with fault injection, an end-to-end
discrepancy demo) demonstrates the six-way action distinction (planned /
proposed / authorized / executor-reported / observed / verified) running as
code. A competitor's slide deck cannot do what the warehouse-putaway demo
does: catch an executor's lie.

Second, the honesty of the differentiation audit (`docs/startup/differentiation.md`):
geometry, the event log, lifecycle mechanics, constraints, provenance
mechanics, temporal queries, all marked **commodity**, explicitly. What
survives the audit is narrow but real: the **claim-vs-observation distinction
as an agent-facing data model** (executor reports and independent observations
stored as separate records and compared), **evidence-addressable belief**
(every belief points to the observations that justify it; contradictory
low-confidence evidence is quarantined), and the **MCP-shaped packaging** for
agent self-interrogation ("why do you believe P17 is there?"). The narrowest
edge is the verification verdicts with evidence IDs — genuinely missing from
stateless MCP-style tool calling, which is the dominant agent pattern.

Third, the pain is budget-proven by adjacent products: drone cycle-count
vendors report customers finding ~$1M in "lost" inventory and 15× count
speedups. Inventory inaccuracy is a costed line item, not a hypothetical.

---

## 2. Biggest unresolved assumption

**The observation feed.** The entire wedge, per-action verification of
putaway/move tasks in an AMR-assisted warehouse, assumes that per-task
media/timestamps (e.g., nav-camera frames at drop time) are available from
fleet managers and correlatable to task-completion events. If the fleet
vendors do not expose per-task media or timestamps, the sidecar must build
its own observation layer (fixed cameras), which changes the unit economics
entirely. This is the single most load-bearing technical assumption in the
program, and it is untested. Everything downstream of it is speculative until
one vendor integration is proven feasible.

Closely behind:

- **Zero customer conversations.** Whether ops managers would pay for
  per-action verification *on top of* periodic drone audits is unknown.
  The wedge's falsifier is stated plainly in the wedge doc: if they say
  "the drone audit next night catches everything we care about," the
  time-value of per-action verification is ~zero and the wedge collapses to
  a feature of the audit stack.
- Green tests prove the discipline is implementable, not that anyone wants it.

---

## 3. Most dangerous technical mistake

**Building the platform instead of the sidecar.** Geometry and spatial
querying are commodity: PostGIS and DuckDB-spatial do them better; our
dependency-free 2D querying is explicitly scaffolding, not the thesis. Any
work that expands spatial analytics, digital-twin scope, slotting
optimization, or visualization plays against our weakest hand and walks
straight into the incumbents' roadmaps (Blue Yonder, Manhattan). The wedge
product is a **verification sidecar**: per-action records with evidence IDs,
fed into the site's *existing* exception queue. Any code that does not serve
the PERCEIVE → REPRESENT → REASON → PLAN → ACT → OBSERVE → VERIFY loop as a
ledger beside the WMS is premature.

The second danger is epistemic, not architectural: **treating the simulator
as viability evidence.** The v0 proves the model can be enforced in code. It
says nothing about adoption, integration friction, or whether the dispute
feed changes operator behavior. A disputed feed nobody reads is shelfware.

---

## 4. Most promising next experiment

Two tracks, in priority order:

1. **The wedge-falsifying conversation** (cheapest, highest information):
   5 ops managers at AMR-assisted warehouses. One question: would you pay
   for per-action verification on top of your nightly drone audits? If the
   answer is "the audit catches everything we care about," the wedge is
   dead and we stop before burning the 09-24 and 09-26 missions on it.
2. **The V1 milestone from the differentiation audit** (most decisive
   technical proof): one documented discrepancy catch on real hardware:
   the layer catching a real executor lie that would have caused
   physical/financial harm. Worth more than the entire v0.

The scheduled missions (09-24 core-loop simulation test, 09-26 reliability
audit) remain useful regardless: they tighten the executable thesis and cost
little. But they must not be mistaken for validation.

---

## 5. What should NOT be built yet

- A full warehouse digital twin, slotting optimization, or any expansion of
  spatial analytics beyond what the verification loop needs. Geometry is
  scaffolding.
- Broader ecosystem integrations (ROS 2, Home Assistant, MCP distribution)
  beyond the single warehouse wedge.
- The "verified action-transition data as training fuel" moat: it requires
  deployments first, and deployments require a wedge that survives contact
  with customers.
- Any UI beyond the CLI/demo harness. No new dependencies.
- Do not re-litigate the wedge: the office/demo scenarios (`office.json`)
  were considered and rejected for good reasons (no budget line, no cost of
  failure). Stay with putaway/move verification until its falsifier is
  tested.

---

## Verdict in one line

The thesis is honest, executable, and narrow, which is why it survives
scrutiny, but it hangs on one untested integration assumption (the
observation feed) and one untested willingness-to-pay assumption. This week's
work should be sized to test those two assumptions, not to widen the code.
