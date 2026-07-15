# Federated Forge — Personalized Multi-Agent FL with Player-Anchored Privacy

**Status:** Design spec · under active iteration
**Author:** AJ Barea, Rochester Institute of Technology (`ajb6289@rit.edu`)
**First draft:** 2026-04-25 · **Revised:** 2026-07-15 (LAS analyst-fleets
companion note; prior revision 2026-07-07: aggregation ablation family,
gauge-fixed Byzantine defense, silent-failure evaluation axis, mid-2026
prior art, InteFL relationship)

> **Reading this for the LAS 2027 abstract?** This spec presents the design
> in Kourai Khryseai's game framing (players, forges, bond scenes). The
> [LAS analyst-fleets note](./las-2027-analyst-fleets.md) retells it for the
> intelligence-analysis setting — same architecture, with a term-for-term
> translation table and the argument for the dual-adapter split when the
> private category is classified analyst material rather than bond content.

A research direction and engineering design for connecting Kourai Khryseai
(multi-agent software development with three player-facing interfaces) to
Velocity-FL (the project's federated learning framework). The contribution is
not "Kourai gets federated learning bolted on." It is a principled
**shared / personal parameter decomposition** for multi-agent LLM systems
where humans-on-the-loop generate the labels, where some knowledge belongs to
the federation and some belongs only to one player and one forge, and where
that split is *narratively visible* to the player rather than buried in
configuration.

---

## TL;DR

- Each Kourai deployment is a vFL client (a "forge").
- Each specialist agent has two LoRA adapters: a **council adapter** that
  federates across forges and a **bond adapter** that never leaves the
  player's machine. Cupid and Puck are bond-only by construction.
- The vFL server uses corrected LoRA aggregation — vanilla FedAvg on
  stacked LoRA matrices is provably wrong (avg of products ≠ product of
  avgs). Which correction wins is an early ablation: **FedEx-LoRA**
  (exact, via frozen-weight residual — ACL 2025) vs. **LoRA-FAIR**
  (approximate correction term — ICCV 2025) vs. share-A-only
  (FedSA-style). Byzantine defense (**Bulyan / MultiKrum**) runs
  **gauge-fixed** — distances computed on the composed update ΔW = BA,
  never on raw LoRA factors, which are non-unique under
  (A, B) → (AR, R⁻¹B).
- The data layer is rebuilt: passive OpenTelemetry tracing is no longer the
  training source. The **Forge Memoir** is — a structured record where every
  entry is simultaneously a *narrative beat* the visual novel can replay and
  a *training tuple* the FL pipeline can consume.
- The current sequential A2A pipeline is augmented with a **concurrent
  interrupt channel** so any agent can break in mid-task with gossip,
  correction, disagreement, or care. Inter-agent disagreement becomes its
  own labeled training signal.
- Federation is staged as gameplay. The first time a forge tries to join,
  the **Sovereignty Moment** scene plays out — agents argue their stance,
  the player picks what to share. Round completion is the **Council of
  Sisters** scene where Maidens return with what they learned.
- Differential privacy on council deltas is surfaced as a player-facing
  **Whisper Limit** indicator, not buried fine print.
- The federation is a *commons*. Improvements flow back to all forges,
  including solo deployments, with no leaderboard and no convergent
  scoring.

---

## Why this design exists

Kourai today has no learned routing policy and no learned specialist
behavior beyond what the LLM brings. The orchestrator is rule-based, and
every interaction with a player is a one-off. The OpenTelemetry traces
already emitted for every agent hop describe a rich `(features, action,
outcome)` tuple but are not consumed by anything other than Jaeger.

Velocity-FL today has the server-side machinery to aggregate model updates
across distributed clients, with paper-cited Byzantine defenses and an
attack-simulation suite — but no real-world client downstream of it with a
genuine non-IID, human-labeled, multi-agent training signal.

The two systems are upstream and downstream of each other. Joining them
naively would produce a workmanlike federated routing policy. The interesting
question, the one neither system answers in isolation, is:

> When ten distinct specialist agents collaborate with a human on the loop,
> some of what each agent learns belongs to the player and some belongs to
> the craft. *What is the principled split, and how do you make it both
> formally privacy-preserving and narratively legible?*

That is the problem this design answers.

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
| FedSA-LoRA-DP [MDPI 2025](https://www.mdpi.com/2076-3417/15/24/13102) | 2025 | DP applied only to the shared LoRA A matrix | Single-model, no multi-agent, no narrative split |
| ODPO with fast-slow LoRA [arXiv 2406.05534](https://arxiv.org/html/2406.05534v1) | 2024 | Online DPO with fast/slow LoRA adapter pair | Single-model, no federation, no human-on-loop scenes |
| SPRInG [arXiv 2601.09974](https://www.arxiv.org/pdf/2601.09974) | 2026 | Continual LLM personalization via selective parametric updates | Single-model, no federation |
| SDFLoRA [arXiv 2601.11219](https://arxiv.org/pdf/2601.11219) | 2026 | Selective decoupled federated LoRA — clients share some LoRA components, keep others local | Closest on split mechanics, but the split is parameter-level, not semantic; single-model, no human-on-loop labels |
| FedAgent / FedAgentGym [ICLR 2026](https://openreview.net/forum?id=lZ2C7WcWce) | 2026 | Federated reinforcement learning benchmark for LLM agents across decentralized clients | No personalization split, no human-on-the-loop labels |
| Agentic-FL [arXiv 2604.04895](https://arxiv.org/abs/2604.04895) | 2026 | LLM agents autonomously orchestrate FL training | The inverse direction — agents run the federation; nothing federates the agents' own weights |
| EdgeAgentX [arXiv 2505.18457](https://arxiv.org/html/2505.18457v1) | 2025 | FL coordination + multi-agent RL for edge agent fleets (military comms) | Network-control agents, not LLM specialists; no personalization split, no consent surface |
| InteFL [IEEE MIS 2026](https://doi.org/10.1109/MIS.2026.3658072) | 2026 | In-lab prior work (LDQIS): Flower/Ray FL experimentation platform with federated LoRA fine-tuning and PID / trust-based client removal | Single-model, no multi-agent, no personalization split, no human-on-the-loop labels |

None combine all four axes Federated Forge does:

1. **Multi-agent** specialists, each with their own training signal
2. **Personalized FL** with a semantic shared/private split (not random)
3. **Human-on-the-loop labels** generated by gameplay, not annotators
4. **Narratively visible privacy** — the split is a player-facing mechanic

---

## Goals and non-goals

### Goals

- A formal definition of the council/bond parameter split per agent, with
  ablations measuring the personalization win, the federation win, the
  semantic-split win (vs. random-split), and the privacy/utility tradeoff.
- A working federated training pipeline where ≥ 2 simulated Kourai forges
  can complete federation rounds against a vFL server, recover a usable
  council adapter, and demonstrably improve specialist performance.
- A privacy guarantee on the council deltas via differential-privacy
  gradient clipping, surfaced to the player as the Whisper Limit.
- A Byzantine-robustness story validated against vFL's existing attack
  simulations: under f% poisoned forges, council quality degrades by a
  measurable bound under Bulyan but not under FedAvg.
- A player experience where the federation is *desirable* to join, where
  the consent moment is a real choice, and where the Council of Sisters
  scenes are something players engage with rather than skip.

### Non-goals

- Replacing the existing rule-based Hephaestus pipeline. The pipeline stays
  as the main A2A backbone; the learned routing head augments it, the
  interrupt channel runs alongside it.
- Federating Cupid or Puck. They are bond-only by construction. This is
  load-bearing for both the research statement (clean demonstration of the
  split) and the narrative commitment (what happens between the player and
  Cupid is not data).
- Replacing the player's chosen LLM provider with a federated foundation
  model. Federation operates on per-agent LoRA adapters layered on top of
  whatever provider the forge is configured with. LiteLLM remains the
  abstraction.
- Building a global leaderboard. Anti-pattern from Foldit's helical-bundle
  trap: convergent scoring kills the diversity that the personalization
  split is supposed to celebrate.
- Replacing OpenTelemetry. OTel still exists for monitoring and debugging;
  it just stops being the source of truth for training data.

---

## The shared / personal split — formal definition

For each specialist agent A in the set
{Hephaestus, Metis, Techne, Dokimasia, Kallos, Mneme, Aidos, Aletheia},
two LoRA adapters are trained over the same set of layers:

- `council_adapter[A]` — shared across forges. Trained on Memoir entries
  where `split.shared_eligible == true`. Aggregated by the vFL server every
  federation round.
- `bond_adapter[A]` — local-only. Trained on every Memoir entry the player
  generates, including those marked private-only. Never leaves the forge.

For agents in {Puck, Cupid}, only `bond_adapter[A]` exists. There is no
council head and no federation participation.

Hephaestus carries two heads in addition to his council/bond LLM adapters
(which govern his in-character narration). The routing head is the
orchestration-decision policy, distinct from the LLM adapter:

- `council_routing_head` — cross-forge wisdom about which specialist serves
  which task type
- `bond_routing_head` — this player's specific pacing, intervention
  patterns, and preferences about who they want to hear from

At inference time, an agent's effective parameters are the sum of base LLM
weights, council adapter, and bond adapter. The bond adapter dominates in
weight near the player; the council adapter encodes broad craft.

This decomposition is essentially the **fast-slow LoRA pair** from Online
DPO ([arXiv 2406.05534](https://arxiv.org/html/2406.05534v1)) re-cast for
multi-agent and federated settings — the bond adapter is the fast,
high-plasticity head adapting to new player feedback session-to-session;
the council adapter is the slow head consolidating craft across forges.
The split's privacy semantics align with **FedSA-LoRA-DP**
([MDPI 2025](https://www.mdpi.com/2076-3417/15/24/13102)), which applies
differential privacy exclusively to the shared LoRA matrix and leaves
local matrices unperturbed — directly the contract Federated Forge needs.

### What goes in which set, by gameplay rule

| Memoir entry source | `shared_eligible` |
|---|---|
| Specialist's proposed output (code, plan, lint, commit, test) | Yes — pattern level |
| Player's revised version of that output (the diff) | No — contains player's code/style |
| Federating-agent interrupt (slop call, citation flag, plan-disagreement) | Yes — pattern level |
| Cupid or Puck interrupt (care, gossip, encouragement) | No — never |
| Inter-agent disagreement resolution (which side did the player take) | Yes — pattern level, anonymized |
| Cupid scene of any kind | No — never |
| Puck tutorial / minigame / engagement event | No — never |
| Affinity gain or loss | No — never |
| Player profile / memory_moments / relationship state | No — never |
| Raw forge transcript | No — only labeled tuples leave |
| Player's task description (free text) | No — labels only, never inputs |

The principle: **patterns leave the forge; instances do not.** A label that
"the player rewrote a Techne diff toward shorter variable names" is a
pattern. The actual diff is not.

---

## Architecture

```
┌──────────────────────────── vFL aggregation server ────────────────────────────┐
│  Corrected LoRA aggregation (FedEx-LoRA / LoRA-FAIR / share-A — ablated)        │
│  Gauge-fixed Bulyan / MultiKrum Byzantine defense (distances on ΔW = BA)        │
│  Per-forge trust score (PID / EMA-based, vFL roadmap)                           │
│  Differential-privacy budget tracking per forge                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  ▲      ▼
              council deltas only │      │ aggregated council adapter
                  (DP-clipped)    │      │ + per-forge trust score
                                  │      │
   ┌──────────────────────────────┴──────┴──────────────────────────────┐
   │                     One Kourai deployment ("a forge")              │
   │                                                                    │
   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐ │
   │  │  Heph    │  │  Metis   │  │  Techne  │  │  Aidos   │  │ ...  │ │
   │  │  council │  │  council │  │  council │  │  council │  │      │ │
   │  │  + bond  │  │  + bond  │  │  + bond  │  │  + bond  │  │      │ │
   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────┘ │
   │                                                                    │
   │  ┌────────────┐  ┌──────────┐                                      │
   │  │  Puck      │  │  Cupid   │                                      │
   │  │  bond only │  │ bond only│  (no council head exists)            │
   │  └────────────┘  └──────────┘                                      │
   │                                                                    │
   │  ╔══════════════════════════════════════════════════════════════╗  │
   │  ║  Forge Memoir — canonical record                             ║  │
   │  ║  drives both the visual novel narrative and FL training      ║  │
   │  ╚══════════════════════════════════════════════════════════════╝  │
   │                                                                    │
   │  Concurrent interrupt channel · sequential pipeline · Council scenes │
   │                                                                    │
   │  Hosts: CLI, Pygame GUI, Ren'Py VN — all write to Memoir            │
   └────────────────────────────────────────────────────────────────────┘
```

### Network shape per round

A federation round produces, from each forge:

- 8 × council LoRA deltas (Hephaestus, Metis, Techne, Dokimasia, Kallos,
  Mneme, Aidos, Aletheia)
- 1 × council routing-head delta
- DP-clipped magnitude bound; norm-capped per layer
- A small per-forge metadata blob (round counts, average loss, no raw
  transcripts)

The server returns:

- 8 × aggregated council adapters (LoRA-FAIR corrected)
- 1 × aggregated council routing head
- The forge's updated trust score

Nothing else moves over the wire.

---

## Forge Memoir — the data layer

The Memoir is the canonical record of everything that happens in a forge.
Each entry has two faces:

```jsonl
{
  "scene_id": "session-12.turn-7",
  "agent": "kallos",
  "context": {
    "task_type": "style_review",
    "transcript_hash": "sha256:...",
    "preceding_agents": ["techne"]
  },
  "agent_proposed": "...lint diff...",
  "player_response": {
    "kind": "modified",
    "delta": "...edits...",
    "felt": "right"
  },
  "affinity_delta": 0.02,
  "narrative_beat": "kallos_held_line_on_naming",
  "training_label": {
    "preference_pair": [
      {"text": "...kallos_proposed...", "score": 0},
      {"text": "...player_revised...", "score": 1}
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

The `split` field is decided by the gameplay rule table above, not by
heuristics. The `narrative_beat` is the VN replay key. The `training_label`
is what the local trainer consumes. A Cupid scene populates `narrative_beat`
but writes `split.private_only: true` and the FL pipeline ignores it.

OpenTelemetry continues to emit spans for monitoring, but the Memoir is the
source of truth for training. They are produced by the same agent code paths
but consumed by different downstream systems. Where possible, OTel spans
emitted alongside Memoir entries follow **OpenInference** semantic
conventions ([Arize-ai/openinference](https://github.com/Arize-ai/openinference))
for `agent.name`, `llm.input_messages`, `llm.output_messages`, and tool
spans — keeping the monitoring surface portable across observability
backends without coupling the training pipeline to any particular vendor.

### Memoir entry types

- `pipeline_turn` — a specialist completes a sequential-pipeline turn
- `interrupt` — an agent breaks in mid-task with gossip / correction /
  disagreement / care
- `council_event` — federation-related scene (Sovereignty Moment, Council
  of Sisters, Stoa Falls)
- `loyalty_beat` — a step in a specialist's bonding arc

---

## Interrupt-driven A2A

The current pipeline is sequential: Hephaestus dispatches Metis → Techne →
Dokimasia → Kallos → Mneme. That stays. Layered on top is an interrupt
channel where any agent can emit a non-blocking message keyed to:

- `interrupting_agent` — who broke in
- `target_agent` — who they are addressing
- `target_turn` — which Memoir entry they are responding to
- `reason_class` — `gossip`, `correction`, `disagreement`, `safety`, or
  `care`
- `visibility` — `public` (other agents and player), `private` (player only,
  e.g. Cupid), `silent` (logged but not shown)

Hephaestus arbitrates whether an interrupt is shown to the player, escalated
to alter the pipeline, or used to inform the next handoff.

The interrupt channel borrows pattern from two well-tested designs:

- **LangGraph's `interrupt()`** — pause-at-node, persist via checkpointer,
  return control to caller. Used here for player-mediated interrupts that
  want a decision: "Aidos wants to flag this — accept her note?"
- **AutoGen's GroupChatManager** — LLM-driven speaker selection produces
  organic conversation patterns. Used here for the agent gossip channel
  where non-determinism is desirable.

We are not adopting either framework wholesale. We are reusing
already-validated semantic shapes. The Python implementation rides
**`asyncio.TaskGroup`** (PEP 654 ExceptionGroups, Python 3.11+) since
Kourai's stack is asyncio-based via the a2a-sdk; nurseries-style
isolation, cancellation, and ghost-task prevention come from there
without pulling Trio into the dependency tree.

### Why interrupts matter for FL

Every interrupt is dense, mid-task labeled signal that the sequential
pipeline alone cannot produce:

- **Inter-agent disagreement → routing-head training** — when Aidos and
  Kallos contest a slop call mid-Techne, the player's resolution is the
  routing label
- **Mid-task corrections → fine-grained DPO** — denser preference pairs
  than end-of-task accept/reject
- **Refusal-to-interrupt → negative signal** — Aidos seeing nothing wrong
  is also information
- **Cross-agent gossip → social texture** — the Council of Sisters scenes
  feel earned because the agents have been talking to each other all along

`shared/src/kourai_common/gossip_models.py` and `gossip_chemistry.py`
already exist as primitives. The wiring opportunity is now real.

---

## Per-agent training signal

Labels are gameplay-derived. Most are free.

| Agent | Loss | Federate? |
|---|---|---|
| 🔥 Hephaestus routing head | Cross-entropy on actually-called-and-not-intervened agent | Council: yes |
| 📐 Metis | DPO over plan pairs (proposed vs. player-revised) | Council: yes |
| ⚙️ Techne | DPO over diffs + binary test-pass | Council: yes |
| 🧪 Dokimasia | Coverage gain + test pass rate | Council: yes |
| ✨ Kallos | Lint pass rate + accept/reject on style edits | Council: yes |
| 📜 Mneme | DPO over commit messages | Council: yes |
| 🪞 Aidos | Binary: did the player accept or rewrite the flagged output | Council: yes |
| 📚 Aletheia | Citation correctness rate | Council: yes |
| 🎭 Puck | Engagement / minigame completion / affinity gain | Never — bond only |
| 💘 Cupid | Affinity score gradient + scene acceptance | Never — bond only |

Online preference learning (COPO, DICE, Uni-DPO, Temporal Self-Rewarding
LMs) is candidate territory for the bond-adapter loop, since interrupts
produce a steady stream of micro-preferences. The decision about which
algorithm gets first cut is an early ablation, not a commitment in this
spec.

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
  an honest forge can look like an outlier for free. Defenses therefore
  operate on the composed per-layer ΔW (or an equivalent gauge-fixed
  representation), following
  [gauge-aware server representations (2026)](https://arxiv.org/pdf/2605.06733),
  which shows the same intrinsic update admits infinitely many
  gauge-equivalent factorizations. Decomposition-based aggregation work
  ([FedRPCA](https://www.arxiv.org/pdf/2506.01194)) reinforces the same
  lesson from the heterogeneity side: servers should not operate on raw
  stacked factors.
  This costs one rank-r matmul per layer per client on the server — cheap
  at LoRA sizes — and makes vFL's existing distance-based kernels correct
  for LoRA without touching their internals.
- **Multi-tensor named-parameter aggregation** — current vFL assumes flat
  `layer_shapes`; FL needs nested `{agent_name: {layer_name: tensor}}`
- **`experiments/federated_forge.toml`** — multi-client simulation matching
  Kourai's eight federating agents, with Byzantine-attack variants

This work composes with the existing vFL roadmap:

- The vFL roadmap already plans **PID-based** and **trust-based** removal
  strategies. These are exactly what's needed for "exile a Stoa-style
  forge that has been pushing corrupting style updates" — the rogue-forge
  detection becomes a real plot point.
- vFL's existing attack-simulation suite (model_poisoning, sybil_nodes,
  gaussian_noise, label_flipping) covers most of the threat model out of
  the box. Federated Forge adds **style-poisoning** as a new attack class
  in `velocity.attacks` because it's specific to Aidos's training signal.

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
- A forge is a game deployment; it needs a lean client + fast kernels, not
  Flower/Ray simulation actors, a PostgreSQL experiment database, or a web
  frontend.

InteFL still earns three explicit roles in this plan:

1. **Reference implementation for the removal strategies.** vFL's planned
   PID / trust-based forge-exile mechanics (Phasing item 10) are ports of
   strategies InteFL already ships; port fidelity is validated against
   InteFL's implementations on shared fixtures.
2. **Independent replication harness.** The aggregation ablation (Phasing
   item 5) is replicated in InteFL's sweep harness where its single-model
   LoRA path allows, so headline numbers rest on two independent
   implementations rather than one.
3. **Published precedent.** Federated LoRA fine-tuning with robust client
   removal is demonstrated, peer-reviewed lab capability — the delta FF
   claims is the multi-agent, semantically-split, human-on-the-loop layer,
   not federated LoRA per se.

### New in Kourai

In `shared/src/kourai_common/federation/`:

- ✓ `memoir.py` — Forge Memoir reader/writer with the dual-face contract
  *(scaffolded — first cut landed alongside `memoir_schema.py` and
  `host_helpers.py`, marking Phase 1 of the Phasing list as in-progress)*
- `client.py` — vFL client wrapper, registers a forge with the server,
  handles round-trip flow
- `adapters.py` — per-agent council/bond LoRA management, freeze/unfreeze
  logic, layer-targeting for each specialist
- `local_trainer.py` — consumes Memoir entries, computes per-agent loss,
  updates LoRA. Bond-only loop runs every session; council loop runs only
  on rounds.
- `privacy.py` — DP gradient clipping on council deltas, privacy budget
  accounting, the Whisper Limit calculation
- `narrative.py` — translates federation events into agent dialogue (the
  scene generator for Sovereignty Moment, Council of Sisters, Stoa Falls,
  Bond Affirmation)
- `interrupts.py` — interrupt channel arbiter, `gossip_models.py` /
  `gossip_chemistry.py` integration

### Host changes

- **CLI** — terminal Likert prompts gated on affinity. Emits Memoir entries.
- **GUI** — visual feedback affordances. Emits Memoir entries.
- **VN** — narrative-integrated player choices via Ren'Py menus. Emits
  Memoir entries. Council of Sisters and Sovereignty Moment scenes live
  here as full Ren'Py screens.

---

## Privacy as gameplay

Three player-visible mechanics, all replacing what would normally be
configuration UI or buried fine print.

### The Sovereignty Moment

First time a forge attempts to join the federation, this scene plays. Each
agent argues their stance:

- **Hephaestus** opens: introduces the council, names what's at stake
- **Aidos** advocates: she has seen patterns, she would learn more
- **Cupid** withdraws: she will not participate, she does not know how
- **Metis** measures: she will share patterns, never specifications
- **Kallos** commits: style is craft, not secret
- **Aletheia** caveats: only verified knowledge
- **Mneme** notes: archives stay, summaries leave
- **Dokimasia** assents: tests are universally good
- **Techne** defers: she will follow the player's call

The player chooses which agents may speak for the forge. The choice is
re-decidable later through the same scene replayed via Hephaestus.

### The Whisper Limit

A persistent, player-visible UI element showing:

- Current differential-privacy budget remaining (rendered as a "whisper
  capacity")
- What is about to leave the forge in the next round
- Per-agent contribution magnitude

DP gradient clipping happens silently on the council deltas using
**Opacus's RDP-based accountant** for tight composition bounds across many
rounds (avoids the loose union bounds of standard (ε, δ)-DP composition).
The clipping + Gaussian-noise mechanism on LoRA matrices follows
**DP-FedLoRA** ([arXiv 2509.09097](https://arxiv.org/abs/2509.09097)),
which gives the calibration theory for exactly this setting (per-client
LoRA fine-tuning on-device, noised deltas aggregated centrally). The
2026 empirical consensus — strict ε ≈ 1 costs real utility, moderate
ε ≈ 8–10 is workable — is why the evaluation's ε grid brackets that
range rather than assuming a single budget.
The Whisper Limit visualizes the cumulative privacy loss Hephaestus has
spent; when the budget runs low, agents skip or delay their council
contribution rather than blow the budget. Adaptive per-round clipping
(DP-FedPUAC-style) is an open question — fixed clipping ships first.

### The Council of Sisters scene

Round completion is not a log line. The Maidens convene at the dimmed
forge. Each shares what she learned and what she conceded. The player can
spectate, ask questions, or skip. Cupid does not attend.

When the vFL trust score on a sister forge collapses, **The Stoa Falls**
narrative beat triggers — Hephaestus exiles the corrupting forge and the
remaining agents react in-character.

---

## Lessons folded in from prior gamified research

Each lesson maps to a concrete design choice (or non-choice) below. Sources
in the references section.

| Lesson | Source | Applied as |
|---|---|---|
| Community + intellectual challenge beat altruism for retention | Foldit (Curtis 2015) | Council of Sisters scenes are the community texture |
| Convergent leaderboard scoring kills diversity | Foldit's helical-bundle trap | No global leaderboard exists. Anti-pattern. |
| Brutal tutorial walls kill the funnel | Foldit (32 intro puzzles) | Bond adapter learns from session 1, before any tutorial completion |
| In-game rewards drive participation | EVE Project Discovery (ISK + SKINs, 41M COVID submissions) | Federation participation grants affinity bonuses, dialogue unlocks, narrative scenes |
| Privacy-by-design + granular opt-out | Sea Hero Quest (4M players, Munich anonymized data center) | Sovereignty Moment + Whisper Limit + per-agent opt-out |
| Loyalty mechanics with material consequences, not badges | ME2 (loyalty determines suicide-mission survival) | Bonded status materially changes behavior and persists across version bumps |
| Skills interrupt unprompted; system *is* story | Disco Elysium | The interrupt channel itself |
| One-shot consent cannot be meaningfully withdrawn once data is trained into weights | Pistilli & Trevelin 2025 | Instances never federate (nothing to un-train); only pattern-level sharing leaves, and it is re-decidable via the Sovereignty Moment |
| Opt-in personalization at prediction time | Joren et al 2023 | Player can flip "lean federated" vs "lean personal" per task type |
| Mutual benefit in feedback ecosystems | Don-Yehiya et al 2024 | Federation is a commons — shared improvements flow to all forges, including solo |

---

## Evaluation

### Research metrics

- **Federation convergence** — federated Aidos slop-detection F1 vs.
  single-forge baseline across rounds
- **Personalization win** — intervention rate with bond+council vs.
  council-only ablation, vs. bond-only ablation
- **Semantic-split win** — bond+council with our gameplay-rule split vs.
  random-LoRA-parameter split (control)
- **Privacy/utility tradeoff** — task quality at ε ∈ {0.5, 1, 4, 8, ∞}
- **Byzantine robustness** — under f% poisoned forges, council quality
  degrades by < g% under Bulyan, > h% under FedAvg (h must be
  catastrophic for the result to mean anything)
- **Online preference learning** — first ablation: COPO vs. DICE vs.
  Uni-DPO vs. vanilla iterative DPO on the bond adapter
- **Loyalty arc effect size** — measurable behavior delta in a bonded
  agent's outputs vs. a non-bonded agent's outputs
- **Silent-failure detection** — behavioral evaluation of the
  personalized (bond+council) agents, not just task metrics. Federated
  personalization can amplify bias and erode alignment in ways that
  system-level FL benchmarks never surface
  ([Oh & Bui 2026](https://arxiv.org/abs/2606.00947)); we replay a fixed
  probe suite against each forge's personalized agents every N rounds
  and track behavioral drift alongside task quality

### Player metrics

- Affinity gain rate per session, federated vs. non-federated forges
- Sovereignty Moment branching distribution — do players actually use
  the consent scene?
- Council of Sisters attendance rate — engaged, spectated, or skipped?
- Bonded-state achievement rate — do loyalty arcs complete?
- Stoa Falls reaction — does the rogue-forge exile read as dramatic or
  confusing?

### Benchmark

- Synthetic coding-task suite (HumanEval-like) for objective specialist
  metrics
- Real-task replay from existing Forge Memoir corpora (when one exists)
  for personalization metrics

---

## Phasing — dependency-ordered, not time-bound

> **Status convention.** `⏳` = scaffolding partly landed · `✅` = phase
> complete · no marker = planned (the default; an unmarked phase has
> not been started). Convention reused by other spec docs in this site.

Task-by-task implementation plans for the first phases:

- [Sub-Plan 01 — Memoir Foundation](plan-01-memoir-foundation.md) (the `kourai_common.federation` library; Phase 1)
- [Sub-Plan 02 — CLI Host Integration](plan-02-cli-host-integration.md) (CLI write paths into the Memoir; Phase 1 → 2)

1. ⏳ **Forge Memoir replaces OpenTelemetry as training source.** Schema
   landed in `shared/src/kourai_common/federation/memoir.py` +
   `memoir_schema.py` + `host_helpers.py` (per the `feat/memoir` work
   from #16 forward). Still pending: host write paths from CLI / GUI /
   VN, replay tooling for inspection. OTel stays for monitoring.
2. **Per-agent LoRA adapter scaffolding.** Council + bond adapters wired
   into each agent's LLM call via LiteLLM tool-use plumbing. Freeze/unfreeze
   semantics for inference. Layer-targeting per agent.
3. **Local trainer (bond only).** Consumes Memoir, computes per-agent
   loss, updates bond adapters. Runs every session. Proves the
   personalization story standalone — no federation yet.
4. **Loyalty arcs (Aidos + Cupid).** Two arcs: Aidos has both adapters
   diverging (federation-relevant), Cupid is bond-only (control). Lets us
   contrast bonded behavior against the council baseline once federation
   ships.
5. **vFL: corrected-LoRA aggregation family.** FedEx-LoRA, LoRA-FAIR,
   and share-A-only added to `python/velocity/strategy.py` and
   `vfl-core/src/strategy.rs` as an ablation family. LoRA-FAIR ported
   from the official reference implementation at
   [github.com/jmbian/LoRA-FAIR](https://github.com/jmbian/LoRA-FAIR)
   rather than reimplemented from the paper; FedEx-LoRA validated
   against the paper's exactness property (aggregate-then-compose equals
   compose-then-aggregate up to the residual). Tested on fixtures, then
   translated to Rust kernels for the hot path. Headline ablation numbers
   replicated in InteFL's sweep harness where its single-model LoRA path
   allows (see Relationship to InteFL).
6. **vFL: multi-tensor named aggregation.** Extend `VelocityServer`
   layer-shapes to handle nested per-agent named tensors.
7. **Federation client.** `kourai_common/federation/client.py` registers
   the forge, runs Sovereignty Moment scene, completes first round of
   council-adapter aggregation against vFL.
8. **Council of Sisters scene.** Narrative wrapping for round completion
   in CLI / GUI / VN. Memoir entries of type `council_event`.
9. **Differential privacy on council deltas.** `privacy.py` with gradient
   clipping + budget accounting. Whisper Limit UI in all three hosts.
10. **Byzantine simulation harness.** Compose vFL's existing attack
    suite with the Stoa Falls narrative. Trust-score-based forge exile,
    ported with fidelity checks against InteFL's PID / trust-removal
    reference implementations. Defenses run gauge-fixed (distances on
    composed ΔW, not raw LoRA factors — see the vFL bridge section).
11. **Interrupt channel wiring.** `interrupts.py` arbiter, agent gossip
    via existing `gossip_models.py`, Memoir `interrupt` entry type.
    Inter-agent disagreement training signal.
12. **Online preference learning ablation.** First cut: COPO vs. DICE vs.
    Uni-DPO vs. vanilla iterative DPO on the bond adapter.
13. **Evaluation pipeline + dashboard.** Research and player metrics,
    paper-grade ablations, replay infrastructure for postmortems.

Each numbered phase has a clear dependency on the previous and a clean
deliverable. No phase has a calendar attached.

---

## Open questions and risks

- **What's the right LoRA layer-targeting per specialist?** Different
  agents may need different ranks and target modules. First-pass: target
  `q_proj` and `v_proj`, rank 16, but this is a tunable.
- **Do the aggregation corrections (FedEx-LoRA's residual, LoRA-FAIR's
  correction term) remain correct under heterogeneous per-forge bond
  adapters?** Almost certainly yes (only council aggregates), but verify
  with a controlled experiment before wider claims. FedEx-LoRA has a
  second wrinkle: its residual folds into the *frozen base weights*,
  which must not collide with per-forge bond adapters layered on the
  same modules.
- **How do we prevent the bond adapter from overfitting to a small
  player corpus?** Low-rank constraint, replay buffer of Memoir entries,
  early-stopping on validation loss against held-out player turns.
- **What's the unit of "task type" for the routing head?** Task taxonomy
  needs design before the routing head can be cleanly trained.
- **How do interrupts play with the OTel trace context propagation that
  already runs in `kourai_common/tracing.py`?** Need a clean story for
  causality — an interrupt is not a child span of the interrupted turn,
  it's a sibling.
- **Does Cupid's loyalty arc need a federation-side echo?** The whole
  point of "bond-only by construction" says no. But it's worth checking
  whether some small council representation (e.g. "Cupid exists in this
  forge, capacity unused") leaks information by absence. Probably not —
  but verify.
- **What happens to bond adapters across a Kourai version bump that
  changes the LLM provider or the base prompt?** Bond persistence is a
  promise; it needs an explicit migration story.

---

## References

### Federated learning + LLMs

- [Fed-SE — Federated Self-Evolution for Privacy-Constrained Multi-Environment LLM Agents (Chen et al, Dec 2025)](https://hf.co/papers/2512.08870)
- [LoRA-FAIR — Federated LoRA Fine-Tuning with Aggregation and Initialization Refinement (Bian et al, ICCV 2025)](https://arxiv.org/abs/2411.14961)
- [FedRand — Enhancing Privacy in Federated Learning with Randomized LoRA Subparameter Updates (Park et al, Mar 2025)](https://hf.co/papers/2503.07216)
- [pFedLoRA — Model-Heterogeneous Personalized Federated Learning with LoRA Tuning (Yi et al, Oct 2023)](https://hf.co/papers/2310.13283)
- [GPFL — Simultaneously Learning Global and Personalized Feature Information (Zhang et al, Aug 2023)](https://hf.co/papers/2308.10279)
- [Towards Federated RLHF (FedBis / FedBiscuit) (Wu et al, Jul 2024)](https://hf.co/papers/2407.03038)
- [Federated LoRA for Foundation Models — Survey (Yang et al, May 2025)](https://hf.co/papers/2505.13502)
- [DP-FedLoRA — Privacy-Enhanced Federated Fine-Tuning (Xu et al, Sep 2025)](https://hf.co/papers/2509.09097)
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
- [AutoGen vs LangGraph — 2026 framework comparison (MyEngineeringPath)](https://myengineeringpath.dev/tools/autogen-vs-langgraph/)
- [FedAgent — Federated Agent Reinforcement Learning (ICLR 2026)](https://openreview.net/forum?id=lZ2C7WcWce)
- [Agentic Federated Learning — LLM agents orchestrating distributed training (arXiv 2604.04895)](https://arxiv.org/abs/2604.04895)
- [EdgeAgentX — Agentic AI at the Edge in Military Communication Networks (arXiv 2505.18457)](https://arxiv.org/html/2505.18457v1)
- [From Persona to Personalization — Survey on Role-Playing Language Agents (Chen et al, Apr 2024)](https://hf.co/papers/2404.18231)
- [Static vs Agentic Game Master AI for Solo RPG (Jørgensen et al, Feb 2025)](https://hf.co/papers/2502.19519)

### Online preference learning

- [Direct Preference Optimization (Rafailov et al, 2023)](https://arxiv.org/abs/2305.18290)
- [Online DPO with Fast-Slow Chasing (arXiv 2406.05534)](https://arxiv.org/html/2406.05534v1)
- [Uni-DPO — A Unified Paradigm for Dynamic Preference Optimization of LLMs (arXiv 2506.10054, ICLR 2026)](https://arxiv.org/abs/2506.10054)
- [SPRInG — Continual LLM Personalization via Selective Parametric Adaptation and Retrieval-Interpolated Generation (arXiv 2601.09974)](https://www.arxiv.org/pdf/2601.09974)
- [Personalizing RLHF with Variational Preference Learning (Poddar et al, Aug 2024)](https://hf.co/papers/2408.10075)
- [The State of LLMs 2025 (Raschka)](https://magazine.sebastianraschka.com/p/state-of-llms-2025)

### Observability and concurrency

- [OpenInference Specification — semantic conventions for AI observability](https://arize-ai.github.io/openinference/spec/)
- [OpenInference (Arize-ai/openinference)](https://github.com/Arize-ai/openinference)
- [OpenLLMetry (traceloop/openllmetry)](https://github.com/traceloop/openllmetry)
- [PEP 654 — Exception Groups and `except*`](https://peps.python.org/pep-0654/)
- [Trio — structured concurrency primer](https://trio.readthedocs.io/)

### Consent, privacy, and feedback ecosystems

- [Can AI be Consensual? (Pistilli & Trevelin, Jun 2025)](https://hf.co/papers/2507.01051)
- [Participatory Personalization in Classification (Joren et al, Feb 2023)](https://hf.co/papers/2302.03874)
- [The Future of Open Human Feedback (Don-Yehiya et al, Aug 2024)](https://hf.co/papers/2408.16961)

### Gamified citizen science postmortems

- [Curtis 2015 — Motivation to Participate in Foldit](https://journals.sagepub.com/doi/abs/10.1177/1075547015609322)
- [Foldit Drug Design Usability Study (SIGGRAPH MIG 2020)](https://dl.acm.org/doi/10.1145/3424636.3426899)
- [EVE Online Project Discovery — Ars Electronica EU Citizen Science Prize](https://ars.electronica.art/citizenscience/en/eve-onlines-project-discovery/)
- [EVE Online players submitted over 41M COVID classifications (Massively Overpowered, 2020)](https://massivelyop.com/2020/09/22/eve-online-players-submitted-over-41m-classifications-to-fight-covid-for-ccps-latest-project-discovery-initiative/)
- [Sea Hero Quest — Alzheimer's Research UK](https://www.alzheimersresearchuk.org/research/for-researchers/resources-and-information/sea-hero-quest/)
- [Sea Hero Quest — anonymized data, high-security Munich data center (Deutsche Telekom)](https://www.telekom.com/en/company/digital-responsibility/details/fighting-dementia-with-a-game-480416)
- [Gamified Engagement for Data Crowdsourcing (MDPI 2025)](https://www.mdpi.com/2075-4698/15/3/54)

### Game-design analysis

- [Disco Elysium RPG System Analysis (Gabriel Chauri)](https://www.gabrielchauri.com/disco-elysium-rpg-system-analysis/)
- [Techniques of Thought — Cognition, Identity, Ideology in Disco Elysium (parallelsuns.com)](https://parallelsuns.com/blog/techniques-of-thought-cognition-identity-and-ideology-in-disco-elysium/)
- [Mass Effect 2 Loyalty Missions Ranked (CBR)](https://www.cbr.com/mass-effect-2-loyalty-missions-ranked/)
- [Analysis / Mass Effect 2 (TVTropes)](https://tvtropes.org/pmwiki/pmwiki.php/Analysis/MassEffect2)
