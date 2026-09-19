# REALITY — Customer Wedge Research

**Date:** 2026-09-19 (startup program, Week 1 Saturday mission)
**Scope:** one concrete operational workflow, not "spatial intelligence"
broadly. This document narrows to a single wedge, the buyer who feels
the pain, the current stack, why it fails, and the smallest product that
could displace it. Assumptions are marked as such.

**Selected wedge: per-action verification of putaway/move tasks in an
AMR-assisted warehouse.** The specific workflow: a robot (or a
human+scanner, but robots are the sharper case) reports "move complete"
for inventory it transported to a destination location, and the warehouse
management system (WMS) records that report as fact. The gap between the
report and reality is the product's entire reason to exist.

---

## 1. The specific user

**Title:** Warehouse Operations Manager or Director of Inventory Control
at a mid-market 3PL (third-party logistics provider), 50–500k sq ft,
running an AMR fleet (e.g., Locus Robotics, 6 River Systems, OTTO Motors)
alongside a mainstream WMS (Manhattan, Blue Yonder, Oracle WMS).

**Why this buyer, specifically:**
- They own the KPI this wedge moves: **inventory accuracy** (record vs.
  actual), and the cost of its failure: failed picks, stockouts,
  "lost" pallets, write-offs, and expedited cycle counts.
- They are **budget-proven**: they already pay for drone-based cycle
  counting (Gather AI, Verity) and/or labor for manual counts. This is
  not a category-creation sale; it is a faster/better sale into an
  existing line item.
- 3PLs feel inventory inaccuracy as direct margin loss — a missed pick
  means SLA penalties and chargebacks, not just an internal metric.
- A mid-market 3PL has a real robot fleet (so the executor/observation
  split exists) but no in-house robotics/ML team (so they will not just
  build the verification layer themselves).
- **Assumption (unverified):** we have had zero customer conversations
  to date. Everything about the buyer in this section is inferred from
  product-market adjacency, not from interviews. Falsify with 5+
  conversations before any code beyond v0.

---

## 2. The painful workflow (concrete, step by step)

1. The WMS issues a task: "move pallet P-4471 (SKU X, qty 40) to slot
   A-23-4-2."
2. An AMR transports the pallet. Its fleet manager reports
   `task_complete` to the WMS.
3. The WMS writes: **P-4471 is in A-23-4-2.** This is now the system's
   belief. There is no second signal.
4. Hours or days later, a picker (or the next robot) goes to A-23-4-2
   and finds it empty — or finds the wrong SKU, or a short count.
5. The discrepancy enters an exception queue. Inventory control sends a
   human to hunt: walk the adjacent slots, check recent move history,
   scan barcodes, reconcile. Each exception costs 15–45 minutes of
   trained labor and usually ends with "adjust and write off."
6. If the error is found only at month-end audit, a customer shipment
   short-ships or a slot shows phantom stock — the most expensive
   failure mode.

The pain is not that errors happen (errors are constant); the pain is
that **the WMS learns about them hours to days after the action that
caused them**, when the causal trail is cold. The operator cannot
answer "which action put the wrong pallet in A-23-4-2?" — only "the
record is wrong now."

---

## 3. The current solution stack

| Layer | What sites actually use | What it does about the gap |
|---|---|---|
| Fleet manager (Locus/6RS/OTTO) | Task orchestration, throughput metrics | **None.** Its `task_complete` is the executor's self-report — the claim this wedge treats as a claim. |
| WMS (Manhattan/Blue Yonder/Oracle) | System of record for inventory | **None.** It ingests the task report as truth; it has no per-action observation pipeline. |
| Fixed barcode scanners / putaway confirm scans | Worker scans slot label on putaway | Helps when the scanner discipline holds; breaks with missed scans, wrong-label scans, and robot-performed moves where no scan happens at all. |
| Drone cycle counting (Gather AI, Verity) | Periodic autonomous barcode sweeps | Finds discrepancies — but as **snapshots**, typically nightly or weekly. A Geodis deployment reported drones counting 15× faster than manual (Gather AI case study); Gather AI claims customers found ~$1M in "lost" inventory. Strong validation of the *pain*, but the drone cannot say which move caused a discrepancy, and it audits long after the fact. |
| Manual cycle counts | Humans with RF scanners | The fallback. Labor-intensive; a full count of a large facility can take workers up to 90 days (Indianapolis Business Journal). |

**Bottom line:** the entire current stack either (a) trusts the
executor's report, or (b) audits the state long after the action.
Nobody closes the loop **per action, at the moment of execution**.

---

## 4. Why current solutions fail (the gap REALITY occupies)

This is the thesis's six-way distinction (`docs/thesis.md` §3) in
operational dress:

1. **Executor reports are claims, stored as facts.** The fleet manager
   reports "moved P-4471 to A-23-4-2" and the WMS believes it. In
   REALITY's terms, stages 4 (executor-reported success) and 5
   (independently observed outcome) are collapsed into one. Every
   downstream process — slotting, picking, replenishment — reasons on
   an unverified claim.
2. **Audits are periodic, not causal.** Drone sweeps and cycle counts
   detect that the record is wrong; they cannot attribute the error to
   the specific action that introduced it. The exception hunt starts
   from a cold trail.
3. **Robot perception is navigation-grade, not evidence-grade.** AMR
   nav cameras see the world constantly, but their output feeds
   localization — not an independent inventory record. The observation
   source exists on site and is *already paid for*; it is just never
   used as evidence.
4. **Discrepancies have no first-class representation.** There is no
   data structure anywhere in the current stack for "action #418's
   claimed effect is disputed by observation obs-221." REALITY's
   verification verdicts — `verified` / `partially_verified` /
   `failed` / `unknown`, with evidence IDs — are exactly the missing
   record type.
5. **No provenance on beliefs.** When a slot shows the wrong SKU, the
   WMS cannot answer "what observations justify believing P-4471 is in
   A-23-4-2?" — the question `docs/startup/differentiation.md` §2
   identifies as the sharpest edge of the v0.

Note the competitive framing: this wedge does **not** compete with
Gather AI/Verity (they are periodic auditors; the wedge is an
execution-time verifier) and does **not** compete with the fleet
managers (they are the executor being verified). The honest competitive
risk is that a fleet vendor adds per-task photo confirmation natively
— an integration response, not a thesis-killer.

---

## 5. The smallest product that could solve it

**"Verify claimed putaway."** A verification sidecar, not a platform:

- **Input:** the site's existing task-completion events (fleet
  manager → webhook/API) for ONE task type: putaway/move tasks. No new
  hardware, no new sensors, no change to how robots work.
- **Observation:** one independent source per zone — e.g., the
  destination slot's fixed camera frame, or the AMR's own nav-camera
  frame at drop time, timestamped within a small window of the claimed
  completion. Barcode-readable is a bonus, not a requirement; presence/
  absence + label read is enough to start.
- **State:** a per-action record — proposed → authorized → executed
  (claimed) → observed → verified/disputed/unknown — exactly the v0
  lifecycle, with evidence IDs. This is REALITY's core loop running as
  a ledger beside the WMS, not replacing it.
- **Output:** an exception feed into the *existing* cycle-count/
  exception queue, prioritized by recency and confidence: "3 moves in
  Zone B in the last hour are disputed or unobserved; the exception
  hunt starts warm, not cold." Plus one queryable answer the WMS
  cannot give today: "what evidence supports this location's record?"
- **What it is NOT:** not a WMS, not a fleet manager, not a robot, not
  a drone replacement, not spatial analytics, not a digital twin.

**First deployment shape (deliberately tiny):** one site, one zone
(e.g., Zone B putaways), one observation feed, one task type. Success
is measured in *exception-hunt labor hours avoided* and *dispute catch
rate* over a 2–4 week pilot — not in features.

---

## 6. Wedges considered and rejected

| Candidate | Why rejected |
|---|---|
| Office hot-desk/workstation provisioning (the `office.json` demo) | Pain is real but shallow: the buyer is an office manager with no budget line and no operational cost of failure. Low willingness to pay. |
| Smart-home / building routines | Crowded (Home Assistant et al.), consumer price sensitivity, no credible wedge into revenue. |
| Last-mile delivery confirmation ("package actually delivered") | Crowded; photo-confirmation already commoditized; margin-poor and litigation-shaped. |
| Picking verification ("right item picked") | Strong pain, but pick stations already have scan-gun confirmation discipline and camera tunnels (e.g., PackageX-style vision); the claim-vs-observation gap is narrower here. Weaker than putaway, where robot moves often have *no* confirmation scan at all. |
| Full warehouse digital twin / slotting optimization | "Spatial intelligence" broadly — exactly the scope this mission excludes. Platform-shaped, long sales cycle, competes with Blue Yonder/Manhattan roadmaps. |

Putaway/move verification wins on: (a) a real, costly, daily workflow;
(b) a budget-proven buyer; (c) an existing-but-unused observation
source (nav cameras); (d) no credible incumbent owning the per-action
verification record; (e) deployable as a sidecar without replacing
anything.

---

## 7. Evidence ledger (honest accounting)

**Evidence we have:**
- The pain is market-validated: Gather AI's customers report finding
  ~$1M in inventory deemed lost; Taylor Logistics cites 87% efficiency
  gain over physical cycle counting (Gather AI materials, via
  RetailTechInnovationHub); Geodis reports 15× faster counts
  (TechTarget, 2026-06). Misplaced pallets/write-offs cost firms
  "millions annually" (Pulse/IERA 2026 coverage of Verity). Industry
  inventory-distortion cost estimates run into the trillions (IHL
  Group via industry press — treat vendor-cited figures as directional,
  not precise).
- Adjacent products validate the *demand for discrepancy detection*;
  none of them verify *per action at execution time* — the gap is real
  in the surveyed stack.
- The v0 executable specification exists: 93 passing tests, an
  end-to-end discrepancy demo (warehouse putaway with a caught executor
  lie), and the differentiation audit
  (`docs/startup/differentiation.md`) defending the claim-vs-observation
  data model as the differentiated piece.

**Evidence we do NOT have:**
- Zero customer conversations. We do not know whether ops managers
  would pay for per-action verification on top of periodic drone
  audits, or whether they see it as redundant.
- Zero hardware integration. The observation feed ("nav-camera frame
  at drop time") is *assumed available and timestamp-correlatable* —
  the single most load-bearing technical assumption. If fleet vendors
  do not expose per-task media or timestamps, the observation source
  must be built (fixed cameras), which changes the unit economics
  entirely.
- No pricing signal, no pilot site, no measured dispute-catch rate.
- No proof that dispute records change operator behavior (a disputed
  feed nobody reads is shelfware).

**What would falsify this wedge:** if ops managers say "the drone
audit next night catches everything we care about" — i.e., if the
time-value of per-action verification is ~zero to them — the wedge
collapses to a feature of the audit stack. The 09-20 (Sun) review and
09-22 (Tue) MVP missions should be built to test exactly this.

---

## Sources

- TechTarget, "Autonomous warehouse drones streamline inventory
  control" (2026-06-17):
  https://www.techtarget.com/ai/feature/Autonomous-warehouse-drones-streamline-inventory-control
- RetailTechInnovationHub, Gather AI inferred case counting
  (2024-04): https://retailtechinnovationhub.com/home/2024/4/17/startup-gather-ai-offers-warehouses-drone-powered-inferred-case-count-and-location-occupancy-capabilities
- Indianapolis Business Journal, "Warehouse drones scan codes to help
  track inventory": https://www.ibj.com/articles/warehouse-drones-scan-codes-to-help-track-inventory
- Inside Logistics, "Drone-powered scanning for inferred case counting
  and location occupancy": https://www.insidelogistics.ca/products/drone-powered-scanning-for-inferred-case-counting-and-location-occupancy/
- aviationfile.com, Verity drones overview:
  https://www.aviationfile.com/verity-drones-revolutionizing-warehouse-automation-with-autonomous-inventory-technology/
- Pulse, "Verity Wins 2026 IERA Award":
  https://www.pulse.bot/robotics/news/iera-award-2026-goes-to-flying-warehouse-robots-by-verity-from-switzerland-4f52d9ce-44b8-40ba-82ff-7206f5f1e948/

Repo-internal: `docs/thesis.md`, `docs/startup/differentiation.md`,
`research/adjacent-tech.md`.
