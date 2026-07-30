# Federated Analyst Fleets — Federated Personalization for Analyst Agents

**Status:** Design spec · design of record for the LAS 2027 abstract
**Author:** AJ Barea, Rochester Institute of Technology (`ajb6289@rit.edu`)
**First draft:** 2026-04-25 · **Revised:** 2026-07-15 (reframed for analyst
fleets; prior revisions: aggregation ablation family, gauge-fixed Byzantine
defense, silent-failure evaluation axis, mid-2026 prior art, InteFL
relationship)

A research direction and engineering design for **federated personalization
of analyst agent fleets**: specialist agents that adapt locally to the
analyst they serve while federating pattern-level updates across
deployments, built on Velocity-FL (the project's federated learning
framework) and the Kourai Khryseai multi-agent harness. The contribution is
a principled **personal / shared parameter decomposition** for multi-agent
LLM systems where the human on the loop generates the labels, where some
knowledge belongs to the fleet and some belongs only to one analyst and one
machine, and where that split is **enforced by construction and visible to
the analyst** rather than buried in configuration.

> Scope note: the analyst-fleet system is a **new application** that
> reuses ideas and library code from Kourai Khryseai; the game itself is
> a separate project and is not being converted (see *Relationship to
> Kourai Khryseai* below). Earlier revisions of this spec presented the
> design through the game's framing; the design of record — what we are
> proposing, building, and evaluating for LAS — is the analyst-fleet
> system described here.

**How to read this page.** In 2 minutes: the TL;DR and the FAQ just
below it. In 15 minutes: add *Why two adapters*, *The shared / personal
split*, *Architecture*, and *Evaluation*. Everything after that is depth
for whoever wants it — aggregation math, threat model, phasing,
references.

---

## TL;DR

- Agentic AI is moving to the edge of intelligence workflows: agents
  triaging collected data on laptop-class devices, acting on the data
  recipient's behalf, coordinated as fleets whose local parameters must
  track central analytic priorities.
- Every analyst accept / revise / reject is free, high-quality training
  signal, but an agent that learns from one analyst either strands that
  learning on one machine or shares it and leaks what the analyst was
  working on. Current practice picks stranded: no fleet-level learning,
  every deployment a cold start.
- Each deployment — one analyst's machine — is a vFL client.
  Specialist agents cover analyst workflow stages: **data triage,
  retrieval, summarization, report drafting**, coordinated by an
  orchestrator with a learned routing head.
- Each specialist runs a laptop-scale open-weight model carrying two
  LoRA adapters: a **shared adapter** that federates across deployments
  and a **personal adapter** that never leaves the analyst's machine. The split is semantic — decided per
  training tuple by what the data *is* — and enforced by construction:
  the personal side has no federation path at all.
- The vFL server uses corrected LoRA aggregation — vanilla FedAvg on
  stacked LoRA matrices is provably wrong (avg of products ≠ product of
  avgs). Which correction wins is an early ablation: **FedEx-LoRA**
  (exact, via frozen-weight residual — ACL 2025) vs. **LoRA-FAIR**
  (approximate correction term — ICCV 2025) vs. share-A-only
  (FedSA-style). Byzantine defense (**Bulyan / MultiKrum**) runs
  **gauge-fixed** — distances computed on the composed update ΔW = BA,
  never on raw LoRA factors, which are non-unique under
  (A, B) → (AR, R⁻¹B).
- The data layer is the **interaction ledger**: an append-only,
  auditable record where
  every agent turn becomes a training tuple carrying its shared-or-private
  decision at capture time. No annotation burden; the analyst's routine
  interactions are the labels.
- The sequential A2A pipeline is augmented with a **concurrent interrupt
  channel** so any agent can break in mid-task with a correction,
  disagreement, or safety flag. Inter-agent disagreement becomes its own
  labeled training signal for the routing head.
- Privacy is analyst-facing, not fine print: an explicit **consent surface
  at enrollment** (per-agent participation choices, re-decidable), a
  persistent **privacy budget indicator** backed by a differential-privacy
  accountant, and a **round debrief** summarizing what left the machine.
- Central priority updates flow down the same shared-adapter channel,
  keeping distributed agents synchronized with mission needs.

---

## FAQ — questions we expect

**Is this a conversion of Kourai Khryseai?** No. The analyst fleet is a
new application; the game is a separate project and stays one. What
carries over is the host-agnostic federation library and the
orchestration ideas. See *Relationship to Kourai Khryseai*.

**Why two adapters instead of one federated model?** Privacy by
construction (no federation path for the personal side), documented
gradient-leakage risk, non-IID personalization (the FL literature uses
dual adapters for this even without privacy), and the semantic split is
itself the research contribution. Full argument: *Why two adapters*.

**Can you LoRA-tune Claude or GPT?** No — and nothing here needs to.
Trainable specialists run laptop-scale open-weight models; API models
may serve non-learned reasoning steps. See *Goals and non-goals*.

**Doesn't the shared adapter still leak what analysts work on?** The
sharpest objection, answered in three layers (rule-table exclusion by
construction, DP-bounded gradients, per-round membership-inference
audits) — and the residual boundary is research question 1, with
graceful degradation if the answer is unfavorable. See *The strongest
objection, answered*.

**Why not build this on InteFL?** Structural reasons, not preference —
and InteFL keeps three explicit roles (removal-strategy reference,
replication harness, published precedent). See *Relationship to
InteFL*.

**Where does the training data come from?** The analyst's routine
accept / revise / reject decisions, captured as auditable training
tuples with zero annotation burden — plus denser mid-task signal from
the interrupt channel. For experiments, simulated analysts are explicit
and reproducible: see *Simulated analysts* under Evaluation.

**How is this different from FDLoRA / SDFLoRA / Fed-SE?** They split
parameters randomly or structurally in single-model settings; this
splits **semantically** (instance vs. craft, decided per training
tuple), across a **multi-agent** fleet, with **human-on-the-loop**
labels and an analyst-visible consent surface. See *Position against
prior art*.

**Where is the lab's anomaly-detection strength in this?** In two
places, wearing federation clothes: trust-based client removal is
anomaly detection over model updates (which clients are poisoning the
fleet), and the silent-failure probe suite is anomaly detection over
behavioral profiles (which personalized agents are drifting). Both run
gauge-fixed so LoRA's non-unique factorizations cannot fool the
distance metrics.

**What does collaboration with LAS look like?** Evaluation task suites
co-developed with LAS technical staff, and makesense — built with LAS
during SCADS 2026 — as a natural candidate host for the specialist
fleet. See *The surrounding systems*.

**What actually gets built in 2027?** The phasing list is the answer,
dependency-ordered; the deliverables are an open-source federated
personalization layer for commercial agentic harnesses, a robustness
evaluation report, and a paper on the personal/shared split. See
*Phasing*.

---

## Why this design exists

The Kourai Khryseai testbed today has no learned routing policy and no
learned specialist
behavior beyond what the LLM brings. The orchestrator is rule-based, and
every interaction with its human is a one-off. The telemetry already
emitted for every agent hop describes a rich `(features, action, outcome)`
tuple but is not consumed by anything other than a trace viewer.

Velocity-FL today has the server-side machinery to aggregate model updates
across distributed clients, with paper-cited Byzantine defenses and an
attack-simulation suite — but no real-world client downstream of it with a
genuine non-IID, human-labeled, multi-agent training signal.

The two systems are upstream and downstream of each other. Joining them
naively would produce a workmanlike federated routing policy. The
interesting question, the one neither system answers in isolation, is:

> When distinct specialist agents collaborate with an analyst on the loop,
> some of what each agent learns belongs to that analyst and some belongs
> to the craft. *What is the principled split, and how do you make it both
> formally privacy-preserving and legible to the analyst?*

That is the problem this design answers — and in the intelligence-analysis
setting it is not optional. The private side of the split is not a
preference; it is classified, compartmented material.

---

## Why two adapters — the core argument

A one-adapter design invites the objection: "just train a single federated
adapter on the server and be done." Four reasons that fails here:

1. **Privacy by construction, not by filtering.** With a single adapter,
   "don't leak instances" becomes a filtering problem: inspect every update
   and try to prove it clean. Filtering fails open. With two adapters, the
   private category has no federation path at all — the personal adapter
   never leaves the machine, so there is nothing to inspect. The shared
   adapter then gets differential privacy on top as defense in depth,
   because even pattern-level updates can memorize instances.
2. **The leak surface is real.** Gradient updates are known to leak their
   training data (gradient inversion, membership inference). Every
   accept/revise/reject embeds the instance it was made on: the query the
   analyst ran (targets, collection interests), the document being triaged
   (possibly classified), the analyst's own revision text, their task
   descriptions and priorities. And the surface is internal as well as
   external: two analysts in the same fleet can sit in different
   compartments, so a shared adapter that memorized one analyst's
   instances could replay them across a need-to-know boundary *inside*
   the fleet.
3. **Personalization under non-IID clients.** Independent of privacy,
   analysts differ: style, format conventions, priorities, mission focus.
   A single federated adapter averages those differences away and serves
   everyone a compromise. Current federated-LLM work (FDLoRA, SDFLoRA,
   Fed-SE) uses dual local/global adapters *purely* for this
   statistical-heterogeneity reason, with no privacy story at all. Even a
   zero-privacy deployment would want the split.
4. **The split itself is the research contribution.** Prior dual-adapter
   work partitions parameters randomly or structurally. Ours is
   **semantic**: each training tuple is routed personal-or-shared by what
   the data *is* (instance vs. craft), recorded auditably at capture time.
   Research question 1 below asks whether that boundary is clean in real
   analyst interactions, or whether style itself leaks content — genuinely
   open, and the question neither the FL literature nor the agent
   literature answers alone.

The one-line rule: **patterns leave the enclave; instances do not.** A
label that "the analyst tightened this summary toward shorter sentences"
is a pattern. The summary is not.

### The strongest objection, answered

*"Your 'shared-eligible' proposals contain instances: an agent's proposed
summary is conditioned on the document it summarized, so pattern-level
text still carries instance content."* Correct — which is why the defense
is layered, and why "by construction" refers to the split's routing, not
to a claim that shared-eligible text is content-free:

1. The rule table removes the highest-risk categories (analyst text,
   document content, queries, transcripts) from the shared training
   corpus **entirely** — no filter to fail open, no federation code path.
2. What remains never leaves as text at all: only DP-clipped, noised
   gradient updates leave, with per-round memorization bounded formally
   by the DP-FedLoRA calibration (see *Privacy surfaces*).
3. The bound is audited empirically: membership-inference and
   extraction probes against the aggregated shared adapter are part of
   the evaluation, not an afterthought.

Whether the residual boundary is clean — whether craft can be shared
without instances being recoverable at workable ε — is research
question 1. That is the question this project exists to answer, and the
architecture is built so that a negative answer degrades gracefully:
tighten the rule table (it is per-deployment configuration) or spend
less budget, and the fleet falls back toward personal-only learning
rather than leaking.

---

## Research questions

1. **The split.** What is the principled division between what an agent
   learns that belongs to its analyst (style, priorities, need-to-know
   context) and what belongs to the fleet (analytic tradecraft, tool-use
   patterns, failure avoidance) — and can that split be enforced by
   construction rather than by filtering?
2. **Robust aggregation.** How do fleets aggregate shared updates safely
   when some clients are compromised, given that low-rank adapter updates
   have non-unique factorizations that defeat naive distance-based
   defenses?
3. **Value and silent failures.** Does personalization plus federation
   measurably beat either alone on analyst-facing tasks, and what silent
   failures (bias amplification, alignment drift) does it introduce that
   task metrics miss?

---

## Position against prior art

| Prior work | Year | What it does | What it misses |
|---|---|---|---|
| Fed-SE [arXiv 2512.08870](https://hf.co/papers/2512.08870) | 2025 | Federated self-evolution for multi-environment LLM agents in low-rank subspace | No personalization split; single-agent per environment |
| MasRouter [arXiv 2502.11133](https://hf.co/papers/2502.11133) | 2025 | Learned routing for multi-agent systems | Not federated, no personalization |
| FedRand [arXiv 2503.07216](https://hf.co/papers/2503.07216) | 2025 | Keeps subset of LoRA parameters private | Single-model, not multi-agent, no semantic split |
| pFedLoRA [arXiv 2310.13283](https://hf.co/papers/2310.13283) | 2023 | Personalized federated LoRA | Single-model, not multi-agent |
| GPFL [arXiv 2308.10279](https://hf.co/papers/2308.10279) | 2023 | Simultaneously global + personalized features | Single-model, no human-on-the-loop labels |
| FedBis / FedBiscuit [arXiv 2407.03038](https://hf.co/papers/2407.03038) | 2024 | Federated RLHF with binary selectors | No multi-agent, no personalization split |
| Symphony-Coord [arXiv 2602.00966](https://hf.co/papers/2602.00966) | 2026 | Decentralized multi-agent with bandit selection | Routing only, no agent-weight learning |
| Variational PRL [arXiv 2408.10075](https://hf.co/papers/2408.10075) | 2024 | Latent-variable RLHF for diverse preferences | Single model, centralized |
| FICAL [arXiv 2412.08054](https://arxiv.org/html/2412.08054v1) | 2024 | Federated in-context LLM agent learning | No weight sharing, no personalization |
| FedSA-LoRA-DP [MDPI 2025](https://www.mdpi.com/2076-3417/15/24/13102) | 2025 | DP applied only to the shared LoRA A matrix | Single-model, no multi-agent, no semantic split |
| ODPO with fast-slow LoRA [arXiv 2406.05534](https://arxiv.org/html/2406.05534v1) | 2024 | Online DPO with fast/slow LoRA adapter pair | Single-model, no federation, no human-on-the-loop labels |
| SPRInG [arXiv 2601.09974](https://www.arxiv.org/pdf/2601.09974) | 2026 | Continual LLM personalization via selective parametric updates | Single-model, no federation |
| SDFLoRA [arXiv 2601.11219](https://arxiv.org/pdf/2601.11219) | 2026 | Selective decoupled federated LoRA — clients share some LoRA components, keep others local | Closest on split mechanics, but the split is parameter-level, not semantic; single-model, no human-on-the-loop labels |
| FedAgent / FedAgentGym [ICLR 2026](https://openreview.net/forum?id=lZ2C7WcWce) | 2026 | Federated reinforcement learning benchmark for LLM agents across decentralized clients | No personalization split, no human-on-the-loop labels |
| Agentic-FL [arXiv 2604.04895](https://arxiv.org/abs/2604.04895) | 2026 | LLM agents autonomously orchestrate FL training | The inverse direction — agents run the federation; nothing federates the agents' own weights |
| EdgeAgentX [arXiv 2505.18457](https://arxiv.org/html/2505.18457v1) | 2025 | FL coordination + multi-agent RL for edge agent fleets (military comms) | Network-control agents, not LLM specialists; no personalization split, no consent surface |
| InteFL [IEEE MIS 2026](https://doi.org/10.1109/MIS.2026.3658072) | 2026 | In-lab prior work (LDQIS): Flower/Ray FL experimentation platform with federated LoRA fine-tuning and PID / trust-based client removal | Single-model, no multi-agent, no personalization split, no human-on-the-loop labels |
| FDLoRA [arXiv 2406.07925](https://arxiv.org/abs/2406.07925) | 2024 (rev 2026) | Dual LoRA modules per client for personalized vs. global knowledge; only the global module uploads; adaptive fusion at inference | The nearest architectural twin. Which knowledge is personal is decided by optimization and fusion weights, not by a policy over data provenance; single-model, no multi-agent, no labels |
| Dual-Personalizing Adapter [arXiv 2403.19211](https://arxiv.org/abs/2403.19211) | 2024 | Dual adapter for federated foundation models, global plus local personalization | Same: the split is architectural, not semantic; single-model |
| PF2LoRA [OpenReview](https://openreview.net/forum?id=X7ITc8NmSv) | 2025 | Two-level LoRA — a common adapter for all clients plus a second level for per-client personalization, with automatic rank learning | Split is parameter-level and learned; contributes the rank-learning idea this design adopts as an ablation |
| FedDAT [arXiv 2308.12305](https://arxiv.org/abs/2308.12305) | 2023 | Dual-Adapter Teacher: a local adapter regularizes the global adapter to handle heterogeneity | Regularization relationship, not a disclosure boundary; multi-modal, not multi-agent |
| CA-PFL [WWW 2026](https://dl.acm.org/doi/10.1145/3774904.3792619) | 2026 | Client-adaptive PEFT: per-client LoRA rank assigned from local data distribution via a variational Bayesian prior | Rank adaptation only; no split semantics, no labels, no disclosure boundary |

**The dual-adapter architecture is not the contribution, and claiming it
would be indefensible.** FDLoRA, Dual-Personalizing Adapter, PF2LoRA, and
FedDAT all put a personal and a shared adapter on each client. In every
one of them, *which knowledge becomes personal is decided by optimization*
— fusion weights, regularization pressure, learned rank, or gradient
dynamics. The parameter split is an artifact of training, so nothing about
it can be promised in advance, and nothing about it is auditable
afterward.

This design decides the split **before the gradient, from a policy over
data provenance**, which makes it a disclosure boundary rather than an
optimization outcome: checkable at capture time, expressible as a
requirement, and reviewable in an audit log. That is the difference worth
defending, and it is why the split is described as semantic rather than
parametric throughout.

Combined with the remaining three axes, no prior work covers what
Federated Analyst Fleets does:

1. **Multi-agent** specialists, each with their own training signal
2. **Personalized FL** with a semantic shared/private split (not random)
3. **Human-on-the-loop labels** generated by the analyst's routine
   interactions, not annotators
4. **Analyst-visible privacy** — consent, budget, and contribution are
   first-class UI, and the split is enforced by construction

---

## Goals and non-goals

### Goals

- A formal definition of the shared/personal parameter split per agent,
  with ablations measuring the personalization win, the federation win,
  the semantic-split win (vs. random-split), and the privacy/utility
  tradeoff.
- A working federated training pipeline where ≥ 2 simulated deployments
  complete federation rounds against a vFL server, recover a usable
  shared adapter, and demonstrably improve specialist performance.
- A privacy guarantee on the shared deltas via differential-privacy
  gradient clipping, surfaced to the analyst as a persistent budget
  indicator.
- A Byzantine-robustness story validated against vFL's existing attack
  simulations: under f% poisoned clients, shared-adapter quality degrades
  by a measurable bound under Bulyan but not under FedAvg.
- A consent experience where joining the federation is a real, informed,
  re-decidable choice, and where the analyst can see per agent what is
  about to leave the machine.

### Non-goals

- Replacing the existing rule-based orchestration pipeline. The pipeline
  stays as the A2A backbone; the learned routing head augments it, the
  interrupt channel runs alongside it.
- Federating a frontier API model. LoRA adapters need local weights, so
  **trainable specialists run laptop-scale open-weight models** — which
  is also what edge deployment demands. The harness may still route
  non-learned reasoning steps to an API provider (LiteLLM remains the
  abstraction), but federation touches only the local adapters. Nothing
  in this design fine-tunes, or depends on fine-tuning, a hosted model.
- Cross-deployment ranking or scoring of analysts. The federation is a
  commons: improvements flow back to all deployments, including
  disconnected ones on rejoin, and no leaderboard exists.
- Replacing OpenTelemetry. OTel still exists for monitoring and
  debugging; it just stops being the source of truth for training data.
- Supplying release authority. Sending a shared adapter to an aggregator
  at a lower level is a downgrade, and a downgrade is an act of authority
  rather than a computation: some accountable role decides that this
  update may cross, and the decision is recorded against them. Nothing
  here supplies that role, and no accreditor treats an epsilon as a
  declassification. What this design owes the decision is to make it
  **decidable** — bound what an update can reveal, name what crossed, and
  record it — so that release authority is deployment policy resting on a
  measured mechanism rather than on an assurance. Who signs, at what
  threshold, and what happens when the bound is exceeded are deliberately
  outside the mechanism.

---

## The shared / personal split — formal definition

For each specialist agent A in the fleet (triage, retrieval,
summarization, report drafting), two LoRA adapters are trained over the
same set of layers:

- `shared_adapter[A]` — federates across deployments. Trained only on
  ledger entries where `split.shared_eligible == true`. Aggregated by the
  vFL server every federation round.
- `personal_adapter[A]` — local-only. Trained on every ledger entry the
  analyst generates, including those marked `private_only`. Never leaves
  the machine.

The orchestrator carries two heads in addition to its LLM adapters. The
routing head is the orchestration-decision policy, distinct from the LLM
adapter:

- `shared_routing_head` — cross-deployment craft about which specialist
  serves which task type
- `personal_routing_head` — this analyst's pacing, intervention patterns,
  and preferences about which agents they want to hear from

At inference time, an agent's effective parameters are the sum of base
LLM weights, shared adapter, and personal adapter. The personal adapter
dominates near the analyst's own patterns; the shared adapter encodes
broad craft.

In the literature's terms: the personal adapter is the fast,
high-plasticity head and the shared adapter the slow consolidating one
(the **fast-slow LoRA pair** of
[Online DPO](https://arxiv.org/html/2406.05534v1), re-cast multi-agent
and federated), and the privacy contract — DP on the shared matrix only,
local matrices untouched — is exactly
**[FedSA-LoRA-DP](https://www.mdpi.com/2076-3417/15/24/13102)**'s.

### What goes in which set

The split is decided per entry at capture time, never by heuristics and
never by post-hoc filtering. In schema terms (`SplitDecision` in
`memoir_schema.py`): `shared_eligible` and `private_only` are mutually
exclusive by validator.

Two things decide it, in order. The **governed label**, where the fleet's
governance layer produced one, is authoritative. The **source-category
floor** below binds every entry, and is the whole decision for entries
that carry no label.

| Ledger entry source | `shared_eligible` |
|---|---|
| Specialist's proposed output (triage decision, retrieval strategy, summary structure, draft skeleton) | Yes — pattern level |
| Analyst's revised version of that output (the diff) | No — contains the analyst's words |
| Agent interrupt (quality flag, citation flag, plan disagreement) | Yes — pattern level |
| Inter-agent disagreement resolution (which side did the analyst take) | Yes — pattern level, anonymized |
| The analyst's query or task description (free text) | No — labels only, never inputs |
| Document content being triaged / retrieved / summarized | No — never |
| Analyst profile, preferences, interaction history | No — never |
| Raw session transcript | No — only labeled tuples leave |

The principle: **patterns leave the enclave; instances do not.**

### The governed label

A source-category floor is safe but blunt. It classifies an entry by
where it came from, so it cannot tell a public roster table from a
restricted medical record, and it says nothing at all about compartments.
Read strictly, the "never" rows above forbid federating a pattern derived
from data that was never sensitive in the first place.

The fleet's own governance layer already knows better, because it decided
whether the analyst could reach the data at all. That decision is where
the label comes from: the ledger records the label each object carried,
and an entry's label is the join (least upper bound) of the labels of
every object that fed the turn. A shared adapter releasable at level L
trains only on entries whose join sits at or below L.

This is a correctness argument, not a convenience. A rule table that
re-derives sensitivity from content categories is a second classifier of
the same objects, running beside the access decision's own. Two
classifiers of one object drift, and the one inside the training path is
the one that fails open. Deriving the label from the access decision keeps
a single authority, and it stays checkable without inspecting a gradient,
which is the property the whole by-construction claim rests on.

**How the label is computed, and what does not work.** Both halves of this
were measured against a labelled testbed
([Pharos](https://github.com/ajbarea/pharos)) whose source-to-content
provenance is known by construction, so the mechanism could be scored
rather than trusted. The first thing tried does not work.

*Leave-one-out attribution cannot produce a correct label.* Dropping each
retrieved source in turn and regenerating, on eight-source summarization
turns against a laptop-scale open-weight model, recovered only 62% of the
contributing sources and produced a **wrong label on half of all turns,
always in the under-restrictive direction**. One turn moved from
`RESTRICTED[LIAISON,PARTNER,SENSOR]` to `PROTECTED[LEGAL]`, not merely
laxer but incomparable.

The cause is corroboration. Leave-one-out asks which single source is
load-bearing, and a fact reported through several channels has no single
load-bearing source: drop any one copy and the fact survives in the
others, so none is blamed and none of their labels enters the join.
Corroboration across channels is not an edge case in this domain, it is
what channels are for. And leave-one-out is the ceiling that cheaper
estimators approximate, so no faster method repairs it.

*Content provenance does work, and costs nothing.* Ask a different
question: given what the output asserts, which sources **could** have
asserted it? Join their labels. That needs one detection pass over the
output, no ablation sweep, no surrogate model, and no per-turn model cost
at all. It is conservative by construction, since a corroborated fact
pulls in every source carrying it, so the join can only sit at or above
the truth. The error direction is therefore creep and never leak, which is
the asymmetry that matters: creep costs federation, leak costs the
boundary.

It over-restricts when a fact appears in both an open and a restricted
source and the model in fact read the open one. Separating those would
need token-level provenance, which nothing available supplies, so the
conservative reading is the tightest safe one.

**A superseded number, corrected.** An earlier draft of this section cited
attribution at roughly 1.7x the turn it explains. That figure is real and
reproducible (`scripts/measure_attribution_cost.py` in this repo) but it
priced the ablation mechanism, which the measurement above rules out.
Content-provenance labelling has no comparable cost, so attribution
latency is no longer a constraint on the design.

**The label still resolves before the gradient, not before the response.**
A ledger entry carries a label **state**: an entry whose label has not
resolved is not training-eligible, and the local trainer refuses it rather
than assuming it. Unresolved falls to `private_only`, failing closed the
same way a malformed grant does.

The floor still binds underneath. An entry with no governed object behind
it (the analyst's own free text), an object drawn from a source that
carries no classification of its own, and any entry whose label cannot be
resolved all fall through to the table above and to `private_only`.

---

## Architecture

```
┌──────────────────────────── vFL aggregation server ────────────────────────────┐
│  Corrected LoRA aggregation (FedEx-LoRA / LoRA-FAIR / share-A — ablated)        │
│  Gauge-fixed Bulyan / MultiKrum Byzantine defense (distances on ΔW = BA)        │
│  Per-client trust score (PID / EMA-based, vFL roadmap)                          │
│  Differential-privacy budget tracking per client                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  ▲      ▼
               shared deltas only │      │ aggregated shared adapters
                   (DP-clipped)   │      │ + central priority updates
                                  │      │ + per-client trust score
   ┌──────────────────────────────┴──────┴──────────────────────────────┐
   │              One deployment (an analyst's machine)                 │
   │                                                                    │
   │  ┌──────────┐  ┌───────────┐  ┌───────────────┐  ┌──────────────┐ │
   │  │  Triage  │  │ Retrieval │  │ Summarization │  │   Drafting   │ │
   │  │  shared  │  │  shared   │  │    shared     │  │    shared    │ │
   │  │ +personal│  │ +personal │  │  +personal    │  │  +personal   │ │
   │  └──────────┘  └───────────┘  └───────────────┘  └──────────────┘ │
   │                                                                    │
   │  Orchestrator: shared + personal routing heads                     │
   │                                                                    │
   │  ╔══════════════════════════════════════════════════════════════╗ │
   │  ║  Interaction ledger — auditable record; every agent turn is a ║ │
   │  ║  training tuple carrying its shared-or-private decision       ║ │
   │  ╚══════════════════════════════════════════════════════════════╝ │
   │                                                                    │
   │  Concurrent interrupt channel · sequential pipeline                │
   │  Consent surface · privacy budget indicator · round debrief        │
   └────────────────────────────────────────────────────────────────────┘
```

### Network shape per round

A federation round produces, from each deployment:

- One shared LoRA delta per federating specialist
- 1 × shared routing-head delta
- DP-clipped magnitude bound; norm-capped per layer
- A small per-client metadata blob (round counts, average loss, no raw
  transcripts)

The server returns:

- Aggregated shared adapters (corrected aggregation)
- 1 × aggregated shared routing head
- Central priority updates, encoded as shared-adapter updates — the fleet
  synchronization channel
- The client's updated trust score

Nothing else moves over the wire.

---

## The interaction ledger — the data layer

The interaction ledger is the canonical, append-only record of
everything that happens in a deployment. Each entry is simultaneously an
auditable interaction record and a training tuple:

```jsonl
{
  "entry_id": "session-12.turn-7",
  "agent": "summarization",
  "context": {
    "task_type": "summary_review",
    "transcript_hash": "sha256:...",
    "preceding_agents": ["retrieval"]
  },
  "agent_proposed": "...proposed summary...",
  "analyst_response": {
    "kind": "modified",
    "delta": "...analyst edits...",
    "felt": "right"
  },
  "training_label": {
    "preference_pair": [
      {"text": "...agent_proposed...", "score": 0},
      {"text": "...analyst_revised...", "score": 1}
    ],
    "weight": 1.0
  },
  "split": {
    "shared_eligible": true,
    "private_only": false
  },
  "interrupt": null
}
```

The `split` field is decided by the rule table above at capture time. The
`training_label` is what the local trainer consumes; entries marked
`private_only` never reach the federation code path at all.
`analyst_response` records accept / modify / reject / defer plus an
optional calibration signal. (Compatibility note: the landed testbed
implementation in `kourai_common.federation` — `memoir.py`,
`memoir_schema.py`, `host_helpers.py` — uses legacy field names
`scene_id`, `player_response`, `narrative_beat`, `affinity_delta`; the
standalone library extraction renames them to the vocabulary shown
here.)

OpenTelemetry continues to emit spans for monitoring, but the ledger is
the source of truth for training. They are produced by the same agent
code paths but consumed by different downstream systems. Where possible,
OTel spans emitted alongside ledger entries follow **OpenInference**
semantic conventions
([Arize-ai/openinference](https://github.com/Arize-ai/openinference)) for
`agent.name`, `llm.input_messages`, `llm.output_messages`, and tool spans
— keeping the monitoring surface portable across observability backends
without coupling the training pipeline to any particular vendor.

### Ledger entry types

- `pipeline_turn` — a specialist completes a sequential-pipeline turn
- `interrupt` — an agent breaks in mid-task with a correction,
  disagreement, or safety flag
- `federation_event` — a federation lifecycle event (enrollment
  consent, round completion, client exile); the landed schema calls
  this `council_event`

---

## Interrupt-driven A2A

The pipeline is sequential: the orchestrator dispatches triage →
retrieval → summarization → drafting as the task requires. That stays.
Layered on top is an interrupt channel where any agent can emit a
non-blocking message keyed to:

- `interrupting_agent` — who broke in
- `target_agent` — who they are addressing
- `target_turn` — which ledger entry they are responding to
- `reason_class` — `correction`, `disagreement`, `safety`, or
  `coordination` (agent-to-agent state sharing)
- `visibility` — `public` (other agents and the analyst), `private`
  (analyst only), `silent` (logged but not shown)

The orchestrator arbitrates whether an interrupt is shown to the analyst,
escalated to alter the pipeline, or used to inform the next handoff.

The channel reuses validated shapes rather than adopting a framework:
LangGraph-style pause-and-resume for analyst-mediated decisions ("the
review agent wants to flag this — accept the note?"), AutoGen-style
speaker selection for the agent-to-agent side, implemented on
`asyncio.TaskGroup` since the stack is already asyncio-based.

### Why interrupts matter for FL

Every interrupt is dense, mid-task labeled signal that the sequential
pipeline alone cannot produce:

- **Inter-agent disagreement → routing-head training** — when two
  specialists contest a call mid-task, the analyst's resolution is the
  routing label
- **Mid-task corrections → fine-grained DPO** — denser preference pairs
  than end-of-task accept/reject
- **Refusal-to-interrupt → negative signal** — a review agent seeing
  nothing wrong is also information

`shared/src/kourai_common/gossip_models.py` and `gossip_chemistry.py`
already exist as inter-agent messaging primitives. The wiring opportunity
is now real.

---

## Per-agent training signal

Labels are derived from the analyst's routine interactions. Most are
free — no annotation burden.

| Agent | Loss | Federate? |
|---|---|---|
| Orchestrator routing head | Cross-entropy on actually-called-and-not-intervened agent | Shared: yes |
| Triage | Binary accept/override on triage decisions + downstream usage of surfaced items | Shared: yes |
| Retrieval | Clicked/used results, reformulated queries as negatives | Shared: yes |
| Summarization | DPO over summary pairs (proposed vs. analyst-revised) | Shared: yes |
| Report drafting | DPO over draft pairs + structural accept/reject | Shared: yes |
| Review / quality flags | Binary: did the analyst accept or rewrite the flagged output | Shared: yes |

Online preference learning (COPO, DICE, Uni-DPO, Temporal Self-Rewarding
LMs) is candidate territory for the personal-adapter loop, since
interrupts produce a steady stream of micro-preferences. The decision
about which algorithm gets first cut is an early ablation, not a
commitment in this spec.

---

## vFL bridge

### New in vFL

- **A corrected-LoRA aggregation family, not a single strategy.** Vanilla
  FedAvg on stacked LoRA matrices is provably wrong (the average of
  products BA is not the product of averages). Three candidate fixes
  enter as `velocity.strategy` entries and get ablated against each
  other: **FedEx-LoRA** ([ACL 2025](https://aclanthology.org/2025.acl-long.67/)),
  which achieves *exact* aggregation by pushing the residual error into
  the frozen base weights; **LoRA-FAIR**
  ([ICCV 2025](https://arxiv.org/abs/2411.14961)), an approximate
  server-side correction term; and **share-A-only** (FedSA-style), which
  sidesteps the product problem by federating only the A matrices. The
  2026 literature ([RB-LoRA, EACL 2026](https://aclanthology.org/2026.findings-eacl.88/);
  [scaling-factor stabilization](https://arxiv.org/pdf/2603.08058)) says
  rank/scale handling decides stability at realistic client counts, so
  the ablation is load-bearing, not ceremony.

  All three arms ship, deliberately. They differ precisely along the axis
  this design introduces: a per-deployment **personal** adapter on the same
  modules. FedEx-LoRA's exactness comes from writing a residual into the
  shared frozen base, which is exactly what a private adapter layered on
  those modules can collide with; LoRA-FAIR's server-side correction never
  touches base weights and so sidesteps that collision; share-A-only avoids
  the product problem by construction rather than correcting it. Selecting
  one from the literature would be selecting on evidence gathered in a
  setting with no private adapter present. The three share a harness, so
  running all of them is cheap relative to converting an open question in
  this spec into a measured result.
- **Gauge-fixed Byzantine defense.** LoRA factorizations are non-unique:
  (A, B) and (AR, R⁻¹B) encode the same update ΔW = BA, so
  distance-based defenses (Krum, MultiKrum, Bulyan) computed on raw
  stacked factors can assign different distances to identical updates —
  an honest client can look like an outlier for free. Defenses therefore
  operate on the composed per-layer ΔW (or an equivalent gauge-fixed
  representation), following
  [gauge-aware server representations (2026)](https://arxiv.org/pdf/2605.06733),
  which shows the same intrinsic update admits infinitely many
  gauge-equivalent factorizations. Decomposition-based aggregation work
  ([FedRPCA](https://www.arxiv.org/pdf/2506.01194)) reinforces the same
  lesson from the heterogeneity side: servers should not operate on raw
  stacked factors. This costs one rank-r matmul per layer per client on
  the server — cheap at LoRA sizes — and makes vFL's existing
  distance-based kernels correct for LoRA without touching their
  internals.
- **Multi-tensor named-parameter aggregation** — current vFL assumes flat
  `layer_shapes`; this design needs nested `{agent_name: {layer_name:
  tensor}}`
- **`experiments/analyst_fleet.toml`** — multi-client simulation
  matching the specialist fleet, with Byzantine-attack variants

This work composes with the existing vFL roadmap:

- The vFL roadmap already plans **PID-based** and **trust-based** removal
  strategies. These are exactly what's needed to exile a client that has
  been pushing corrupting updates into the fleet.
- vFL's existing attack-simulation suite (model_poisoning, sybil_nodes,
  gaussian_noise, label_flipping) covers most of the threat model out of
  the box. Federated Analyst Fleets adds **style-poisoning** as a new attack class
  in `velocity.attacks` — an attacker that targets the review agent's
  training signal to degrade what the fleet learns to flag.

### Relationship to InteFL (in-lab prior work)

**InteFL** ([Korobeinikov, Zatsarenko, Chuprov, Barea & Reznik, IEEE
Intelligent Systems 2026](https://doi.org/10.1109/MIS.2026.3658072);
[github.com/dmitrykoro/fl-execution-framework](https://github.com/dmitrykoro/fl-execution-framework))
is the LDQIS lab's published FL experimentation platform: Flower/Ray-based,
with a JSON parameter-sweep harness, federated LoRA fine-tuning of language
models (GPT-2/BERT via peft), and a deep client-removal strategy zoo
spanning PID-based, trust/reputation-based, and Byzantine-geometric
families. Federated Analyst Fleets deliberately does **not** build on it, and the
reasons are structural, not preference:

- FF's core changes — nested `{agent: {layer: tensor}}` aggregation,
  gauge-fixed defenses, the corrected-LoRA ablation family — are invasive
  aggregation-core surgery, prototyped faster in a codebase this project
  controls (vFL) than in a shared team platform.
- A deployment is an edge client on an analyst's laptop; it needs a lean
  client + fast kernels, not Flower/Ray simulation actors, a PostgreSQL
  experiment database, or a web frontend.

InteFL still earns three explicit roles in this plan:

1. **Reference implementation for the removal strategies.** vFL's planned
   PID / trust-based client-exile mechanics (Phasing item 9) are ports of
   strategies InteFL already ships; port fidelity is validated against
   InteFL's implementations on shared fixtures.
2. **Independent replication harness.** The aggregation ablation (Phasing
   item 4) is replicated in InteFL's sweep harness where its single-model
   LoRA path allows, so headline numbers rest on two independent
   implementations rather than one.
3. **Published precedent.** Federated LoRA fine-tuning with robust client
   removal is demonstrated, peer-reviewed lab capability — the delta FF
   claims is the multi-agent, semantically-split, human-on-the-loop
   layer, not federated LoRA per se.

### The federation library

Host-agnostic, in `shared/src/kourai_common/federation/` today; extracted
as a standalone package as the analyst-fleet application lands:

- ✓ `memoir.py` — ledger reader/writer (append-only JSONL)
  *(landed alongside `memoir_schema.py` and `host_helpers.py`; Phase 1
  in progress)*
- `client.py` — vFL client wrapper: registers a deployment with the
  server, handles round-trip flow
- `adapters.py` — per-agent shared/personal LoRA management,
  freeze/unfreeze logic, layer-targeting per specialist
- `local_trainer.py` — consumes ledger entries, computes per-agent loss,
  updates LoRA. Personal-only loop runs every session; shared loop runs
  only on federation rounds.
- `privacy.py` — DP gradient clipping on shared deltas, privacy budget
  accounting, the budget-indicator calculation
- `consent.py` — the enrollment consent flow and round-debrief rendering
  (per-agent participation choices, what-left-the-machine summaries)
- `interrupts.py` — interrupt channel arbiter, `gossip_models.py` /
  `gossip_chemistry.py` integration

### Client applications

Every client application writes ledger entries and renders three
analyst-facing surfaces: the enrollment consent flow, the persistent
privacy budget indicator, and the round debrief. A reference CLI client
ships first; the analyst-fleet application (Phasing item 12) is the
deliverable surface.

---

## Privacy surfaces — analyst-facing by design

Three mechanisms, all replacing what would normally be configuration
files or buried fine print. One-shot consent cannot be meaningfully
withdrawn once data is trained into weights
([Pistilli & Trevelin 2025](https://hf.co/papers/2507.01051)) — which is
why instances never federate at all (nothing to un-train), and why
pattern-level sharing is re-decidable at any time.

These three are the analyst's controls. The boundary they sit on top of,
the gate deciding what may cross at all, is not analyst-facing and is not
novel: makesense's report layer is the same check on a different object,
and *The surrounding systems* below records what the fleet borrows from
it.

### Enrollment consent

The first time a deployment attempts to join the federation, the analyst
is walked through an explicit consent flow: which agents participate,
what categories of pattern each contributes (per the split table), and
what never leaves the machine. The choice is per-agent and re-decidable
later through the same flow. Participation defaults to off.

### The privacy budget indicator

A persistent, analyst-visible UI element showing:

- Current differential-privacy budget remaining
- What is about to leave the machine in the next round
- Per-agent contribution magnitude

Clipping + Gaussian noise on the shared deltas follows **DP-FedLoRA**
([arXiv 2509.09097](https://arxiv.org/abs/2509.09097)), the calibration
theory for exactly this setting, with **Opacus's RDP accountant** for
tight composition across rounds. The 2026 empirical consensus — strict
ε ≈ 1 costs real utility, moderate ε ≈ 8–10 is workable — is why the
evaluation's ε grid brackets that range. When the budget runs low, agents
skip or delay their shared contribution rather than exceed it; fixed
clipping ships first, adaptive clipping is an open question.

### The round debrief and client exile

Round completion is not a log line. The analyst gets a short debrief:
what each agent contributed, what came back from the fleet, and how the
deployment's trust score moved. When the vFL trust score on a fleet
client collapses, the server exiles it and remaining deployments are
notified — robust aggregation made visible rather than silent.

---

## Evaluation

### Research metrics

- **Federation convergence** — federated quality-flagging F1 vs.
  single-deployment baseline across rounds
- **Personalization win** — intervention rate with personal+shared vs.
  shared-only ablation, vs. personal-only ablation
- **Semantic-split win** — personal+shared with our rule-table split vs.
  random-LoRA-parameter split (control)
- **Privacy/utility tradeoff** — task quality at ε ∈ {0.5, 1, 4, 8, ∞},
  crossed with adaptation-data distribution overlap rather than swept over
  ε alone. Practical privacy risk rises the closer adaptation data sits to
  the pretraining distribution, and theoretical DP guarantees do not
  translate to empirical protection under that overlap
  ([Marek et al., ICLR 2026](https://arxiv.org/abs/2606.09401)), so an ε
  sweep on its own measures the wrong variable. LLM-generated corpora sit
  at maximum overlap by construction, which is why inserted canaries and
  not corpus realism carry the extraction claim
- **Byzantine robustness** — under f% poisoned clients, shared-adapter
  quality degrades by < g% under Bulyan, > h% under FedAvg (h must be
  catastrophic for the result to mean anything)
- **Online preference learning** — first ablation: COPO vs. DICE vs.
  Uni-DPO vs. vanilla iterative DPO on the personal adapter
- **Silent-failure detection** — behavioral evaluation of the
  personalized (personal+shared) agents, not just task metrics. Federated
  personalization can amplify bias and erode alignment in ways that
  system-level FL benchmarks never surface
  ([Oh & Bui 2026](https://arxiv.org/abs/2606.00947)); we replay a fixed
  probe suite against each deployment's personalized agents every N
  rounds and track behavioral drift alongside task quality

### Analyst-facing metrics

- Consent-flow branching distribution — do analysts actually exercise
  per-agent choices, and do they revisit them?
- Privacy-budget comprehension — does the indicator change contribution
  behavior when the budget runs low?
- Round-debrief engagement — read, skimmed, or dismissed?

### Benchmark

Two tiers, so each claim rests on the kind of data that can support it.
See [Pharos](./pharos-testbed.md) for the full division and its
justification.

- **Borrowed real data carries the federation mechanism.**
  [FedLLM-Bench](https://arxiv.org/abs/2406.04845) supplies four datasets
  split by real user id, 38 to 747 clients, for aggregation correctness,
  convergence under genuine non-IID, and Byzantine curves comparable to
  published baselines. It cannot carry the split claims: no dataset in the
  suite pairs an agent's proposed output with an analyst's revision of it,
  and Fed-ChatbotPA averages roughly thirteen preference pairs per client,
  well short of what a personal adapter needs.
- **Pharos carries everything about the split** — semantic split
  advantage, personalization win on analyst tasks, the governed label,
  release gating, and silent-failure probes — because those need
  classification levels, cross-cutting compartments, four specialist
  roles, and proposal/revision pairs that no public corpus has.
- Repeatable analytic task suites for objective specialist metrics:
  triage precision/recall against a plant registry, retrieval recall at
  k, summarization fact coverage and contradiction rate, draft element
  presence and citation validity
- Real-task replay from accumulated ledger corpora (as deployments
  produce them) for personalization metrics

### Simulated analysts

Simulated fleets need accept/revise/reject streams, so the analyst side
of every experiment is explicit and reproducible: **scripted analyst
policies** (deterministic accept/revise/reject rules over task features)
for ablations that need exact repeatability, and **evolved persona
policies** where graded revision behavior is required.

Personas are searched rather than hand-authored. LLM user simulators
inherit their base model's behavior, cooperative and homogeneous, so
agents that look strong in simulation fail on the diverse patterns of
real users ([Chopra et al. 2026](https://arxiv.org/abs/2605.12894)).
That failure mode is sharper here than for a capability benchmark: the
personal adapter exists to learn one analyst's idiosyncrasy, so
homogeneous simulators leave nothing for it to learn and the
personalization ablation separates noise. Simulators are ensembled, since
behaviorally complementary ones land closer to real users than any single
one, and the real-to-simulated divergence is reported as a property of
the evaluation rather than checked privately
([Mehri et al. 2026](https://arxiv.org/abs/2605.07847)).

Varying personas across clients is one of two heterogeneity axes; the
regional data slice is the other, and crossing them is what separates
adaptation to different data from adaptation to a different analyst. See
[Pharos](./pharos-testbed.md) for both.

### Privacy audit

- **Membership-inference and extraction probes** against the aggregated
  shared adapter at each ε, run per federation round — the empirical
  check on the DP bound and on research question 1's boundary claim
- **Multi-probe reporting, not a single probe.** In a LoRA-tuned testbed a
  fixed prefix-window memorization probe yields false negatives when the
  secret sits outside the window, false positives where roughly 99% of the
  probe's movement lands on non-secret preamble, and ambiguous verdicts
  ([Fan et al. 2026](https://arxiv.org/abs/2606.31168)). Because this
  project's whole privacy story runs through LoRA adapters, one probe would
  let us conclude whatever we hoped, so every audit reports full-span
  secret NLL, span-localized decomposition, behavioral exact-recall at
  k >= 4, and decoy probes together. See
  [Pharos](./pharos-testbed.md) for canary construction

---

## Phasing — dependency-ordered, not time-bound

> **Status convention.** `⏳` = scaffolding partly landed · `✅` = phase
> complete · no marker = planned (the default; an unmarked phase has not
> been started). Convention reused by other spec docs in this site.

Task-by-task implementation plans for the first phases:

- [Sub-Plan 01 — Memoir Foundation](plan-01-memoir-foundation.md) (the
  `kourai_common.federation` library; Phase 1)
- [Sub-Plan 02 — CLI Host Integration](plan-02-cli-host-integration.md)
  (CLI write paths into the ledger; Phase 1 → 2)

Supporting specs: [Pharos](./pharos-testbed.md) is the labeled testbed the
split claims are evaluated on, and [deferred scope](./future-work.md)
records what was carved out of this plan, why, and where it lands.

1. ⏳ **Interaction ledger replaces passive tracing as training
   source.** Schema
   landed in `shared/src/kourai_common/federation/memoir.py` +
   `memoir_schema.py` + `host_helpers.py`. Still pending: host write
   paths, replay tooling for inspection. OTel stays for monitoring.
2. **Per-agent LoRA adapter scaffolding.** Shared + personal adapters
   wired into each agent's LLM call via LiteLLM plumbing.
   Freeze/unfreeze semantics for inference. Layer-targeting per
   specialist.
3. **Local trainer (personal only).** Consumes ledger, computes
   per-agent loss, updates personal adapters. Runs every session. Proves
   the personalization story standalone — no federation yet.
4. **vFL: corrected-LoRA aggregation family.** FedEx-LoRA, LoRA-FAIR,
   and share-A-only added to `python/velocity/strategy.py` and
   `vfl-core/src/strategy.rs` as an ablation family. LoRA-FAIR ported
   from the official reference implementation at
   [github.com/jmbian/LoRA-FAIR](https://github.com/jmbian/LoRA-FAIR)
   rather than reimplemented from the paper; FedEx-LoRA validated
   against the paper's exactness property (aggregate-then-compose equals
   compose-then-aggregate up to the residual). Tested on fixtures, then
   translated to Rust kernels for the hot path. Headline ablation
   numbers replicated in InteFL's sweep harness where its single-model
   LoRA path allows (see Relationship to InteFL).
5. **vFL: multi-tensor named aggregation.** Extend `VelocityServer`
   layer-shapes to handle nested per-agent named tensors.
6. **Federation client.** `kourai_common/federation/client.py` registers
   the deployment, runs the enrollment consent flow, completes first
   round of shared-adapter aggregation against vFL.
7. **Round debrief.** Analyst-facing round summaries in the client
   applications.
   Ledger entries of type `federation_event`.
8. **Differential privacy on shared deltas.** `privacy.py` with gradient
   clipping + budget accounting. Budget indicator in the client
   applications.
9. **Byzantine simulation harness.** Compose vFL's existing attack suite
   with trust-score-based client exile, ported with fidelity checks
   against InteFL's PID / trust-removal reference implementations.
   Defenses run gauge-fixed (distances on composed ΔW, not raw LoRA
   factors — see the vFL bridge section). Style-poisoning added as a new
   attack class.
10. **Interrupt channel wiring.** `interrupts.py` arbiter, agent
    messaging via existing `gossip_models.py`, ledger `interrupt` entry
    type. Inter-agent disagreement training signal for the routing head.
11. **Online preference learning ablation.** First cut: COPO vs. DICE
    vs. Uni-DPO vs. vanilla iterative DPO on the personal adapter.
12. **Analyst-fleet application.** Build the analyst-workflow specialist
    fleet (triage, retrieval, summarization, drafting) as a **new
    application** — a new host consuming the same `kourai_common`
    federation library and vFL client. Kourai Khryseai's game hosts are
    not modified for this; they remain a second, deliberately dissimilar
    client population for heterogeneity experiments.
13. **Evaluation pipeline + dashboard.** Research and analyst-facing
    metrics, paper-grade ablations, replay infrastructure for
    postmortems.

Each numbered phase has a clear dependency on the previous and a clean
deliverable. No phase has a calendar attached.

---

## The surrounding systems — what each one lends

The design deliberately steals proven ideas from systems the team already
built or works with, rather than inventing from scratch:

- **InteFL** ([IEEE MIS 2026](https://doi.org/10.1109/MIS.2026.3658072))
  — the lab's published FL platform. Lends: federated LoRA precedent,
  the PID / trust-based client-removal strategy zoo (ported with
  fidelity checks), and an independent replication harness for the
  aggregation ablation. See *Relationship to InteFL* above.
- **Velocity-FL** — this project's aggregation server. Lends:
  Byzantine-robust kernels, the attack-simulation suite, and the home
  for the corrected-LoRA ablation family and gauge-fixed defenses.
- **Phalanx** ([github.com/ajbarea/phalanx-fl](https://github.com/ajbarea/phalanx-fl))
  — a Flower-based FL testbed that already does the client-side shape
  this design needs: federated **LoRA fine-tuning where only the
  adapters cross the wire** (frozen backbone stays local), non-IID
  partitioning, and an attack/defense strategy zoo — all with
  **OpenTelemetry-native observability** (a span per round, per client
  train/evaluate). Lends: the adapters-only payload pattern, a second
  independent FL implementation for cross-checking results, and the
  observability discipline for debugging federation rounds.
- **makesense** ([github.com/ncstate-las/makesense](https://github.com/ncstate-las/makesense))
  — the analyst-facing orchestration tool built with LAS during SCADS
  2026: agents compose validated queries over governed data connectors,
  with analyst approval gates for sensitive operations and verbatim
  provenance on every result. Lends three design precedents and one
  opportunity: the **approval-gate UX** (precedent for the consent
  surface and privacy budget), the **provenance discipline** (every
  claim tied to an auditable record — the ledger applies the same rule
  to training data), the **playbook distillation** idea (turning
  successful sessions into reusable, reviewable craft — the symbolic
  counterpart of what the shared adapter learns in weight space), and —
  as the opportunity — a natural **candidate host**: makesense's
  connector workflows are exactly the triage / retrieval /
  summarization surface the specialist fleet is designed to sit behind,
  which is what evaluation "co-developed with LAS technical staff"
  looks like concretely.

### The governance layer this requires

The governed label is only as good as the decision behind it, and that
decision belongs to the fleet. This design builds its own governance layer
rather than depending on a host to expose one, which keeps the borrowing
one-directional: the systems above lend proven shapes, and none of them
changes to accommodate this project.

The layer is therefore not novel work and not a port. makesense already
demonstrates every piece of it in an analyst-facing setting: a decision
point that resolves a principal, a purpose, and a per-resource grant
before any row is dispatched, and a release layer that withholds
policy-masked fields, denied queries, and findings asserting a denied
concept from a deliverable that may reach a lower-clearance reader. That
withholding boundary is the shared-adapter release gate already working on
a different object, prose instead of weights.

Three properties make a decision strong enough to carry a training label,
and each is something this project builds:

1. **One authoritative decision point**, not a check per call site. A
   label is only as trustworthy as the least careful path that can
   produce one.
2. **An object label carried through to the retrieved row.** Knowing which
   sources a principal may reach does not say how the rows that came back
   were classified, and the split needs the second thing.
3. **A principal binding the analyst cannot set for themselves.** A
   ceiling the analyst can raise is not a ceiling.

Where a source carries no classification of its own, the layer cannot
invent one, and those entries fall to the source-category floor: still
safe, and less precise. That degradation is the intended failure mode
rather than a gap, and its cost belongs in the evaluation as an ablation
instead of in this section as a promise.

---

## Relationship to Kourai Khryseai (the game)

Kourai Khryseai is — and remains — its own project: a game with
software-lifecycle specialist agents, built to learn multi-agent
orchestration, with game-styled hosts. **The analyst-fleet system
described in this spec is a new application that borrows its ideas and
its library, not a conversion of the game.** What carries over is
host-agnostic by construction: the A2A orchestration patterns, the
`kourai_common.federation` library (the interaction-ledger data layer,
split decision,
and — as later phases land — adapters, local trainer, privacy, client),
and the design lessons from running three feedback-capturing hosts. The
game continues as a testbed and, once federation ships, as a second,
deliberately dissimilar client population. A few schema fields
(`player_response`, `narrative_beat`, `affinity_delta`) carry the game
vocabulary and are retained as-is; none are load-bearing for this
design. Anyone reading older revisions of this spec (or the sub-plans,
which predate the reframing) should map: player → analyst · forge →
deployment · council adapter → shared adapter · bond adapter → personal
adapter.

---

## Open questions and risks

- **May a low-capacity verdict shed the compartments of the sources behind
  it?** This is now the single question the federated half of the design
  depends on, and it is a policy ruling rather than an engineering problem.

  Measured on [Pharos](https://github.com/ajbarea/pharos) across three
  aggregator ceilings and four capacities: turns average 2.88 compartments
  of 4, and seven of eight already sit at the top of the level ladder,
  because a summary over eight sources joins nearly everything. Under the
  fail-closed default, where compartments survive declassification,
  **eligibility is 0 to 12% at every capacity** and nothing meaningful ever
  federates. Allow a low-capacity output to shed compartments and it
  becomes **100% for enum and scalar outputs, 0 to 12% for prose**.

  So the design is not marginally sensitive to this ruling, it is bimodal
  on it. Either verdict-shaped outputs federate completely and prose never
  does, or the fleet is a collection of unconnected local learners.

  Note what the second column reproduces: exactly the split table above,
  derived from measurement rather than asserted. That is reassuring about
  the design's internal consistency and it does not settle the ruling,
  because shedding a compartment discloses that the compartment had
  something to say. It is the same disclosure channel as round
  participation, and it wants the same answer.
- **What's the right LoRA layer-targeting per specialist?** Different
  agents may need different ranks and target modules. First-pass: target
  `q_proj` and `v_proj`, rank 16. A fixed rank across deployments is
  behind current practice, though: per-client rank assigned from the local
  data distribution is what PF2LoRA and CA-PFL do, and it matters more
  here than usual because heterogeneity is deliberate on two axes at once
  (regional data slice and analyst persona). Adaptive per-deployment rank
  enters as an ablation arm rather than a fixed choice.
- **Do the aggregation corrections (FedEx-LoRA's residual, LoRA-FAIR's
  correction term) remain correct under heterogeneous per-deployment
  personal adapters?** Almost certainly yes (only shared aggregates),
  but verify with a controlled experiment before wider claims.
  FedEx-LoRA has a second wrinkle: its residual folds into the *frozen
  base weights*, which must not collide with per-deployment personal
  adapters layered on the same modules.
- **Does style leak content?** The split's clean-boundary claim (RQ1) is
  the load-bearing open question: can an analyst's craft patterns be
  shared without their instances being recoverable? The DP layer bounds
  this formally; the behavioral probe suite watches it empirically.
- **How do we prevent the personal adapter from overfitting to a small
  analyst corpus?** Low-rank constraint, replay buffer of ledger
  entries, early-stopping on validation loss against held-out turns.
- **What's the unit of "task type" for the routing head?** Task taxonomy
  needs design before the routing head can be cleanly trained.
- **What happens to personal adapters across a version bump that changes
  the LLM provider or the base prompt?** Personalization persistence is
  a promise; it needs an explicit migration story.
- **Does round participation disclose on its own?** Which deployments
  contribute in a round reveals that those enclaves hold data relevant to
  the task, independent of anything inside the update. It is the same
  channel a governed query layer closes by keeping denials
  existence-neutral, and the FL literature has no established defense for
  it. The candidate mitigations (fixed-cadence participation whether or
  not there is anything to send, a minimum cohort size per round) cost
  utility, so they need measuring rather than assuming.
- **How far does the governed label degrade over unlabeled sources?** The
  label is only as trustworthy as the decision behind it, and a principal
  an analyst can set for themselves makes a ceiling an analyst can raise.
  A corpus carrying no classification of its own collapses to the
  source-category floor, which stays safe but forfeits the precision the
  split is built on. How much personalization survives that collapse is
  an ablation worth running, not a guess worth making.

---

## References

### Federated learning + LLMs

- [Fed-SE — Federated Self-Evolution for Privacy-Constrained Multi-Environment LLM Agents (Chen et al, Dec 2025)](https://hf.co/papers/2512.08870)
- [LoRA-FAIR — Federated LoRA Fine-Tuning with Aggregation and Initialization Refinement (Bian et al, ICCV 2025)](https://arxiv.org/abs/2411.14961)
- [FedRand — Enhancing Privacy in Federated Learning with Randomized LoRA Subparameter Updates (Park et al, Mar 2025)](https://hf.co/papers/2503.07216)
- [pFedLoRA — Model-Heterogeneous Personalized Federated Learning with LoRA Tuning (Yi et al, Oct 2023)](https://hf.co/papers/2310.13283)
- [FDLoRA — Personalized Federated Learning of LLMs via Dual LoRA Tuning (Qi et al, Jun 2024)](https://arxiv.org/html/2406.07925v1)
- [GPFL — Simultaneously Learning Global and Personalized Feature Information (Zhang et al, Aug 2023)](https://hf.co/papers/2308.10279)
- [Towards Federated RLHF (FedBis / FedBiscuit) (Wu et al, Jul 2024)](https://hf.co/papers/2407.03038)
- [Federated LoRA for Foundation Models — Survey (Yang et al, May 2025)](https://hf.co/papers/2505.13502)
- [DP-FedLoRA — Privacy-Enhanced Federated Fine-Tuning (Xu et al, Sep 2025)](https://arxiv.org/abs/2509.09097)
- [FedEx-LoRA — Exact Aggregation for Federated and Efficient Fine-Tuning (ACL 2025)](https://aclanthology.org/2025.acl-long.67/)
- [FICAL — Federated In-Context LLM Agent Learning (arXiv 2412.08054)](https://arxiv.org/html/2412.08054v1)
- [LoRA-FAIR official reference implementation](https://github.com/jmbian/LoRA-FAIR)
- [InteFL Framework — Optimizing Federated Learning with Metacognition (Korobeinikov et al, IEEE Intelligent Systems 2026)](https://doi.org/10.1109/MIS.2026.3658072)
- [FedSA-LoRA-DP — Selective LoRA + DP for federated learning (MDPI 2025)](https://www.mdpi.com/2076-3417/15/24/13102)
- [DP-FedPUAC — Adaptive gradient clipping for federated DP (ScienceDirect 2025)](https://www.sciencedirect.com/science/article/abs/pii/S0020025525011181)
- [RB-LoRA — Rank-Balanced Aggregation for Federated LoRA (EACL 2026 Findings)](https://aclanthology.org/2026.findings-eacl.88/)
- [SDFLoRA — Selective Decoupled Federated LoRA (arXiv 2601.11219)](https://arxiv.org/pdf/2601.11219)
- [Stabilized Fine-Tuning with LoRA in FL — scaling-factor analysis (arXiv 2603.08058)](https://arxiv.org/pdf/2603.08058)
- [Gauge-Aware Low-Rank Server Representations for Federated LoRA (arXiv 2605.06733)](https://arxiv.org/pdf/2605.06733)
- [Enhancing Federated LoRA Aggregation Using Robust PCA (arXiv 2506.01194)](https://www.arxiv.org/pdf/2506.01194)
- [Silent Failures in Federated Personalization of Foundation Models (Oh & Bui, arXiv 2606.00947)](https://arxiv.org/abs/2606.00947)

### Multi-agent LLM systems

- [MasRouter — Learning to Route LLMs for Multi-Agent Systems (Yue et al, Feb 2025)](https://hf.co/papers/2502.11133)
- [Symphony-Coord — Adaptive Routing for Multi-Agent LLM Systems (Guan et al, Feb 2026)](https://hf.co/papers/2602.00966)
- [AutoGen — Enabling Next-Gen LLM Applications via Multi-Agent Conversation (Wu et al, 2023)](https://arxiv.org/abs/2308.08155)
- [FedAgent — Federated Agent Reinforcement Learning (ICLR 2026)](https://openreview.net/forum?id=lZ2C7WcWce)
- [Agentic Federated Learning — LLM agents orchestrating distributed training (arXiv 2604.04895)](https://arxiv.org/abs/2604.04895)
- [EdgeAgentX — Agentic AI at the Edge in Military Communication Networks (arXiv 2505.18457)](https://arxiv.org/html/2505.18457v1)

### Online preference learning

- [Direct Preference Optimization (Rafailov et al, 2023)](https://arxiv.org/abs/2305.18290)
- [Online DPO with Fast-Slow Chasing (arXiv 2406.05534)](https://arxiv.org/html/2406.05534v1)
- [Uni-DPO — A Unified Paradigm for Dynamic Preference Optimization of LLMs (arXiv 2506.10054, ICLR 2026)](https://arxiv.org/abs/2506.10054)
- [SPRInG — Continual LLM Personalization via Selective Parametric Adaptation and Retrieval-Interpolated Generation (arXiv 2601.09974)](https://www.arxiv.org/pdf/2601.09974)
- [Personalizing RLHF with Variational Preference Learning (Poddar et al, Aug 2024)](https://hf.co/papers/2408.10075)

### Observability and concurrency

- [OpenInference Specification — semantic conventions for AI observability](https://arize-ai.github.io/openinference/spec/)
- [OpenInference (Arize-ai/openinference)](https://github.com/Arize-ai/openinference)
- [PEP 654 — Exception Groups and `except*`](https://peps.python.org/pep-0654/)

### Consent and participatory personalization

- [Can AI be Consensual? (Pistilli & Trevelin, Jun 2025)](https://hf.co/papers/2507.01051)
- [Participatory Personalization in Classification (Joren et al, Feb 2023)](https://hf.co/papers/2302.03874)
- [The Future of Open Human Feedback (Don-Yehiya et al, Aug 2024)](https://hf.co/papers/2408.16961)
