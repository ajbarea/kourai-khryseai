# Federated Forge for Analyst Fleets: Why Two Adapters (LAS 2027)

**Status:** Companion note to the LAS 2027 abstract *"Federated Personalization
for Fleets of Analyst Agents"* · **Author:** AJ Barea (`ajb6289@rit.edu`)
**Audience:** LDQIS team. This page explains the intelligence-analysis (IA)
direction of the abstract and the design argument behind its central
commitment: two LoRA adapters per agent, one private, one federated.

The full technical design (aggregation ablations, gauge-fixed Byzantine
defense, differential-privacy accounting, phased plan) lives in the
[design spec](./index.md). This page is the shorter "why", retold for the
LAS setting rather than the game setting.

---

## The setting, without the game

The design spec frames everything through Kourai Khryseai's visual-novel
layer: players, forges, bond scenes. Strip that away and the architecture
underneath is exactly what the LAS call asks for in challenge area 3.5
(Agentic AI): fleets of agents at the edge, triaging data on laptops, acting
on the data recipient's behalf, whose local parameters must stay synchronized
with central analytic priorities.

In the LAS framing:

| Design-spec term | LAS / IA term |
| --- | --- |
| Forge (one deployment) | One analyst's machine (FL client) |
| Player | Intelligence analyst |
| Specialist agents (software-dev roles) | Workflow-stage agents: triage, retrieval, summarization, report drafting |
| Bond adapter (local-only) | **Personal adapter**: never leaves the analyst's machine |
| Council adapter (federated) | **Shared adapter**: federates under differential privacy |
| Forge Memoir entry | Auditable training tuple from routine analyst interactions |
| Gameplay split rules | Per-tuple shared-or-private decision, enforced by construction |
| Sovereignty Moment / Whisper Limit | Explicit consent surface + visible privacy budget |

The FL machinery is unchanged: Velocity-FL supplies corrected LoRA
aggregation and Byzantine-robust kernels; InteFL supplies the published
federated LoRA fine-tuning precedent and trust-based client removal.

## The obvious objection

> "Without the romance/bond system, is there still anything private to
> separate? Analyst clients just produce metrics, so why not one adapter,
> trained on the server?"

This objection has it backwards. The game's bond content was a *stand-in*
for a category that intelligence work has natively, and has worse. In the IA
setting the private side is not a narrative flourish; it is classified,
compartmented material.

## What is actually in a training tuple

Every accept/revise/reject an analyst makes embeds the **instance** it was
made on:

- the query the analyst ran (reveals targets and collection interests),
- the document text being triaged or summarized (may be classified),
- the analyst's own revision text and task descriptions,
- their priorities and need-to-know context.

None of that may enter a federated update. Not merely as policy: gradient
updates are known to leak their training data (gradient inversion and
membership-inference attacks), which is exactly why the abstract pairs
federation with differential privacy even for the shared adapter. And the
leak surface is internal as well as external: two analysts in the same fleet
can sit in different compartments, so a single shared adapter that memorized
one analyst's instances could replay them across a need-to-know boundary
*inside* the fleet.

What **is** sharable is task craft: how to sequence tools for a triage pass,
what a well-structured summary looks like, which retrieval strategies fail,
common failure modes to avoid. The spec's one-line rule survives translation
untouched: **patterns leave the enclave; instances do not.**

## Why two adapters, not one

**1. Privacy by construction, not by filtering.** With a single adapter,
"don't leak instances" becomes a filtering problem: inspect every update and
try to prove it clean. Filtering fails open. With two adapters, the private
category has no federation path at all; the personal adapter never leaves
the machine, so there is nothing to inspect. The shared adapter then gets
differential privacy on top as defense in depth, because even pattern-level
updates can memorize instances.

**2. Personalization under non-IID clients.** Independent of privacy,
analysts differ: style, format conventions, priorities, mission focus. A
single federated adapter averages those differences away and serves everyone
a compromise. Current federated-LLM work (FDLoRA, SDFLoRA, Fed-SE) already
uses dual local/global adapters *purely* for this statistical-heterogeneity
reason, with no privacy story at all. So even a zero-privacy deployment
would want the split.

**3. The split itself is the research contribution.** Prior dual-adapter
work partitions parameters randomly or structurally. Ours is **semantic**:
each training tuple is routed personal-or-shared by what the data *is*
(instance vs. craft), recorded auditably at capture time. Research question
1 of the abstract asks whether that boundary is clean in real analyst
interactions, or whether style itself leaks content. That is genuinely open,
and it is the question neither the FL literature nor the agent literature
answers alone.

**4. Fleet synchronization rides the same channel.** The shared adapter is
also the downlink: centrally issued priority updates flow to every client as
shared-adapter updates, which is the "Distributed Agent Management and Fleet
Synchronization" capability the LAS call names explicitly. A one-adapter,
server-trained design would have to build that channel anyway; here it
falls out of the architecture.

## What this means for the team

- **Velocity-FL** (Byzantine-robust aggregation, attack simulation,
  corrected-LoRA ablations) is the shared-adapter server side.
- **InteFL** precedent (federated LoRA, PID/trust-based client removal)
  grounds the robustness claims and gives us reference implementations to
  validate against.
- **Kourai Khryseai's data layer** is the client side: every agent turn is
  already recorded as a training tuple with its shared-or-private decision.
  Re-skinning the specialists from software-dev roles to analyst workflow
  stages (triage, retrieval, summarization, drafting) changes prompts and
  evaluation tasks, not the federation architecture.
- The evaluation plan (personalization/federation ablations, poisoning
  robustness curves, privacy/utility tradeoffs, silent-failure probes) is
  unchanged from the design spec, run on analyst-facing tasks.
