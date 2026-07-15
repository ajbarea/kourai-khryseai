# Federated Forge — Federated Personalization for Analyst Agent Fleets

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
- Each deployment (a **forge** — one analyst's machine) is a vFL client.
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
- The data layer is the **Memoir**: an append-only, auditable record where
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

## Why this design exists

Kourai today has no learned routing policy and no learned specialist
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

None combine all four axes Federated Forge does:

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

---

## The shared / personal split — formal definition

For each specialist agent A in the fleet (triage, retrieval,
summarization, report drafting), two LoRA adapters are trained over the
same set of layers:

- `shared_adapter[A]` — federates across deployments. Trained only on
  Memoir entries where `split.shared_eligible == true`. Aggregated by the
  vFL server every federation round.
- `personal_adapter[A]` — local-only. Trained on every Memoir entry the
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

This decomposition is essentially the **fast-slow LoRA pair** from Online
DPO ([arXiv 2406.05534](https://arxiv.org/html/2406.05534v1)) re-cast for
multi-agent and federated settings — the personal adapter is the fast,
high-plasticity head adapting to new analyst feedback session-to-session;
the shared adapter is the slow head consolidating craft across
deployments. The split's privacy semantics align with **FedSA-LoRA-DP**
([MDPI 2025](https://www.mdpi.com/2076-3417/15/24/13102)), which applies
differential privacy exclusively to the shared LoRA matrix and leaves
local matrices unperturbed — directly the contract Federated Forge needs.

### What goes in which set

The split is decided per entry by a fixed rule table at capture time —
not by heuristics, not by post-hoc filtering. In schema terms
(`SplitDecision` in `memoir_schema.py`): `shared_eligible` and
`private_only` are mutually exclusive by validator.

| Memoir entry source | `shared_eligible` |
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
   │  ║  Memoir — canonical, auditable record; every agent turn is a  ║ │
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

## Memoir — the data layer

The Memoir is the canonical record of everything that happens in a
deployment (implemented in `kourai_common.federation`: `memoir.py`,
`memoir_schema.py`, `host_helpers.py`). Each entry is simultaneously an
auditable interaction record and a training tuple:

```jsonl
{
  "scene_id": "session-12.turn-7",
  "agent": "summarization",
  "context": {
    "task_type": "summary_review",
    "transcript_hash": "sha256:...",
    "preceding_agents": ["retrieval"]
  },
  "agent_proposed": "...proposed summary...",
  "player_response": {
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
`private_only` never reach the federation code path at all. (Field names
follow the landed schema; `player_response` — the analyst's
accept/modify/reject/defer plus an optional calibration signal — and the
testbed-specific fields `narrative_beat` / `affinity_delta` date from the
game-host era and are retained for compatibility until the schema's next
major rev.)

OpenTelemetry continues to emit spans for monitoring, but the Memoir is
the source of truth for training. They are produced by the same agent
code paths but consumed by different downstream systems. Where possible,
OTel spans emitted alongside Memoir entries follow **OpenInference**
semantic conventions
([Arize-ai/openinference](https://github.com/Arize-ai/openinference)) for
`agent.name`, `llm.input_messages`, `llm.output_messages`, and tool spans
— keeping the monitoring surface portable across observability backends
without coupling the training pipeline to any particular vendor.

### Memoir entry types

- `pipeline_turn` — a specialist completes a sequential-pipeline turn
- `interrupt` — an agent breaks in mid-task with a correction,
  disagreement, or safety flag
- `council_event` — a federation lifecycle event (enrollment consent,
  round completion, client exile); schema name retained from the landed
  code

---

## Interrupt-driven A2A

The pipeline is sequential: the orchestrator dispatches triage →
retrieval → summarization → drafting as the task requires. That stays.
Layered on top is an interrupt channel where any agent can emit a
non-blocking message keyed to:

- `interrupting_agent` — who broke in
- `target_agent` — who they are addressing
- `target_turn` — which Memoir entry they are responding to
- `reason_class` — `correction`, `disagreement`, `safety`, or `gossip`
  (agent-to-agent state sharing)
- `visibility` — `public` (other agents and the analyst), `private`
  (analyst only), `silent` (logged but not shown)

The orchestrator arbitrates whether an interrupt is shown to the analyst,
escalated to alter the pipeline, or used to inform the next handoff.

The interrupt channel borrows pattern from two well-tested designs:

- **LangGraph's `interrupt()`** — pause-at-node, persist via
  checkpointer, return control to caller. Used here for analyst-mediated
  interrupts that want a decision: "the review agent wants to flag this —
  accept the note?"
- **AutoGen's GroupChatManager** — LLM-driven speaker selection produces
  organic conversation patterns. Used here for the agent-to-agent channel
  where non-determinism is desirable.

We are not adopting either framework wholesale. We are reusing
already-validated semantic shapes. The Python implementation rides
**`asyncio.TaskGroup`** (PEP 654 ExceptionGroups, Python 3.11+) since the
stack is asyncio-based via the a2a-sdk; nursery-style isolation,
cancellation, and ghost-task prevention come from there without pulling
Trio into the dependency tree.

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
- **`experiments/federated_forge.toml`** — multi-client simulation
  matching the specialist fleet, with Byzantine-attack variants

This work composes with the existing vFL roadmap:

- The vFL roadmap already plans **PID-based** and **trust-based** removal
  strategies. These are exactly what's needed to exile a client that has
  been pushing corrupting updates into the fleet.
- vFL's existing attack-simulation suite (model_poisoning, sybil_nodes,
  gaussian_noise, label_flipping) covers most of the threat model out of
  the box. Federated Forge adds **style-poisoning** as a new attack class
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
families. Federated Forge deliberately does **not** build on it, and the
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

### New in Kourai

In `shared/src/kourai_common/federation/`:

- ✓ `memoir.py` — Memoir reader/writer with the dual-face contract
  *(landed alongside `memoir_schema.py` and `host_helpers.py`; Phase 1
  in progress)*
- `client.py` — vFL client wrapper: registers a deployment with the
  server, handles round-trip flow
- `adapters.py` — per-agent shared/personal LoRA management,
  freeze/unfreeze logic, layer-targeting per specialist
- `local_trainer.py` — consumes Memoir entries, computes per-agent loss,
  updates LoRA. Personal-only loop runs every session; shared loop runs
  only on federation rounds.
- `privacy.py` — DP gradient clipping on shared deltas, privacy budget
  accounting, the budget-indicator calculation
- `consent.py` — the enrollment consent flow and round-debrief rendering
  (per-agent participation choices, what-left-the-machine summaries)
- `interrupts.py` — interrupt channel arbiter, `gossip_models.py` /
  `gossip_chemistry.py` integration

### Host changes

All hosts write Memoir entries and render three analyst-facing surfaces:
the enrollment consent flow, the persistent privacy budget indicator, and
the round debrief. The CLI host is the reference implementation; the GUI
host follows.

---

## Privacy surfaces — analyst-facing by design

Three mechanisms, all replacing what would normally be configuration
files or buried fine print. One-shot consent cannot be meaningfully
withdrawn once data is trained into weights
([Pistilli & Trevelin 2025](https://hf.co/papers/2507.01051)) — which is
why instances never federate at all (nothing to un-train), and why
pattern-level sharing is re-decidable at any time.

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

DP gradient clipping happens on the shared deltas using **Opacus's
RDP-based accountant** for tight composition bounds across many rounds
(avoids the loose union bounds of standard (ε, δ)-DP composition). The
clipping + Gaussian-noise mechanism on LoRA matrices follows
**DP-FedLoRA** ([arXiv 2509.09097](https://arxiv.org/abs/2509.09097)),
which gives the calibration theory for exactly this setting (per-client
LoRA fine-tuning on-device, noised deltas aggregated centrally). The 2026
empirical consensus — strict ε ≈ 1 costs real utility, moderate ε ≈ 8–10
is workable — is why the evaluation's ε grid brackets that range rather
than assuming a single budget. When the budget runs low, agents skip or
delay their shared contribution rather than exceed it. Adaptive per-round
clipping (DP-FedPUAC-style) is an open question — fixed clipping ships
first.

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
- **Privacy/utility tradeoff** — task quality at ε ∈ {0.5, 1, 4, 8, ∞}
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

- Repeatable analytic task suites for objective specialist metrics:
  triage precision/recall on labeled corpora, retrieval nDCG,
  summarization quality (reference-based + rubric), draft acceptance
  rate
- Real-task replay from accumulated Memoir corpora (as deployments
  produce them) for personalization metrics

### Simulated analysts

Simulated fleets need accept/revise/reject streams, so the analyst side
of every experiment is explicit and reproducible: **scripted analyst
policies** (deterministic accept/revise/reject rules over task features)
for ablations that need exact repeatability, and **persona-conditioned
LLM judges** (fixed seeds, fixed rubrics, personas varying style,
format conventions, and priorities) where graded revision behavior is
required. Varying personas across clients is also how the controlled
non-IID populations are constructed — the heterogeneity the
personalization claims are tested against is designed, not incidental.

### Privacy audit

- **Membership-inference and extraction probes** against the aggregated
  shared adapter at each ε, run per federation round — the empirical
  check on the DP bound and on research question 1's boundary claim

---

## Phasing — dependency-ordered, not time-bound

> **Status convention.** `⏳` = scaffolding partly landed · `✅` = phase
> complete · no marker = planned (the default; an unmarked phase has not
> been started). Convention reused by other spec docs in this site.

Task-by-task implementation plans for the first phases:

- [Sub-Plan 01 — Memoir Foundation](plan-01-memoir-foundation.md) (the
  `kourai_common.federation` library; Phase 1)
- [Sub-Plan 02 — CLI Host Integration](plan-02-cli-host-integration.md)
  (CLI write paths into the Memoir; Phase 1 → 2)

1. ⏳ **Memoir replaces passive tracing as training source.** Schema
   landed in `shared/src/kourai_common/federation/memoir.py` +
   `memoir_schema.py` + `host_helpers.py`. Still pending: host write
   paths, replay tooling for inspection. OTel stays for monitoring.
2. **Per-agent LoRA adapter scaffolding.** Shared + personal adapters
   wired into each agent's LLM call via LiteLLM plumbing.
   Freeze/unfreeze semantics for inference. Layer-targeting per
   specialist.
3. **Local trainer (personal only).** Consumes Memoir, computes
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
7. **Round debrief.** Analyst-facing round summaries in the hosts.
   Memoir entries of type `council_event`.
8. **Differential privacy on shared deltas.** `privacy.py` with gradient
   clipping + budget accounting. Budget indicator in the hosts.
9. **Byzantine simulation harness.** Compose vFL's existing attack suite
   with trust-score-based client exile, ported with fidelity checks
   against InteFL's PID / trust-removal reference implementations.
   Defenses run gauge-fixed (distances on composed ΔW, not raw LoRA
   factors — see the vFL bridge section). Style-poisoning added as a new
   attack class.
10. **Interrupt channel wiring.** `interrupts.py` arbiter, agent
    messaging via existing `gossip_models.py`, Memoir `interrupt` entry
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

## Relationship to Kourai Khryseai (the game)

Kourai Khryseai is — and remains — its own project: a game with
software-lifecycle specialist agents, built to learn multi-agent
orchestration, with game-styled hosts. **The analyst-fleet system
described in this spec is a new application that borrows its ideas and
its library, not a conversion of the game.** What carries over is
host-agnostic by construction: the A2A orchestration patterns, the
`kourai_common.federation` library (Memoir data layer, split decision,
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

- **What's the right LoRA layer-targeting per specialist?** Different
  agents may need different ranks and target modules. First-pass: target
  `q_proj` and `v_proj`, rank 16, but this is a tunable.
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
  analyst corpus?** Low-rank constraint, replay buffer of Memoir
  entries, early-stopping on validation loss against held-out turns.
- **What's the unit of "task type" for the routing head?** Task taxonomy
  needs design before the routing head can be cleanly trained.
- **How do interrupts play with the OTel trace-context propagation that
  already runs in `kourai_common/tracing.py`?** Need a clean story for
  causality — an interrupt is not a child span of the interrupted turn,
  it's a sibling.
- **What happens to personal adapters across a version bump that changes
  the LLM provider or the base prompt?** Personalization persistence is
  a promise; it needs an explicit migration story.

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
