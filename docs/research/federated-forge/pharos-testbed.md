# Federated Forge — Pharos, the labeled fleet testbed

**Goal:** supply the one thing no public dataset supplies, a corpus whose
objects carry real classification levels and cross-cutting compartments,
so the governed label has variance and the shared/personal split can be
measured rather than asserted.

**Spec reference:** [`index.md`](./index.md), specifically *The shared /
personal split*, *The governed label*, and *Evaluation*.

## Why this exists

The split is decided by a governed label, and the label is only
meaningful if objects actually differ in sensitivity and compartment.
Every public analyst-adjacent corpus is uniformly unclassified, so a
label derived from it is constant, and an experiment over a constant is
vacuous. Pharos exists to give that label variance.

It is deliberately not a general-purpose benchmark. Federation mechanics
are validated elsewhere, on real data, for reasons the next section makes
explicit.

**What this clears.** Pharos instantiates the label lattice with concrete
elements, and it supplies labeled data so the governed label has variance
and the split is evaluable rather than merely demonstrable.

The third blocker, attribution cost, has since been measured rather than
argued: a 32-pass ContextCite ablation budget over a ten-source
summarization turn costs roughly **1.7x the turn** (1.69x and 1.74x across
two samples), on qwen2.5:7b-instruct on an 8 GB RTX 3060 Ti, per-pass
median 270 ms against a 5.1 s turn. The harness is
`scripts/measure_attribution_cost.py`, so the figure is reproducible rather
than quoted. That rules out synchronous attribution and permits deferred
attribution, which is all the design needs, since the label must resolve
before the gradient rather than before the reply.

Three caveats the measurement does not cover. The ablation budget has to
grow with source count for the linear surrogate to stay identifiable, so a
forty-source retrieval turn is not simply four times this figure. The
Jacobian-based alternative was not measured, for want of a local white-box
stack. And a memory-constrained host stalls: one pass in an early
sixty-four carried 9.7 s, half that sample's total, which is why the
harness reports stalls separately instead of averaging them into the
headline. All three belong in the build order's first step, where the
generator fixes source counts.

## Two tiers, and an honest division of claims

Borrowed real data carries the federation mechanism. Pharos carries
everything about the split.

| Claim | Tier | Why there |
| --- | --- | --- |
| Aggregation correctness (FedEx-LoRA / LoRA-FAIR / share-A) | Borrowed | Comparable to published baselines |
| Federation convergence under real non-IID | Borrowed | Natural client partitions, not designed ones |
| Byzantine robustness curves | Borrowed | Attacker injection over a real partition |
| Semantic split advantage | Pharos | Needs craft-vs-style structure that chat data lacks |
| Personalization win on analyst tasks | Pharos | Needs per-specialist proposal/revision pairs |
| Governed label, release gating, label creep | Pharos | Needs levels and compartments |
| Silent-failure probes on personalized agents | Pharos | Needs the four specialist roles |
| Canary extraction and membership inference | Either | Canaries are inserted, not discovered |

**What the borrowed tier cannot do, stated plainly.**
[FedLLM-Bench](https://arxiv.org/abs/2406.04845) is the right source for
the mechanism claims: four datasets split by real user id, 38 to 747
clients, with diversity across language, quality, quantity, instruction,
length, embedding, and preference. It is the wrong source for the split
claims, for two measured reasons. Fed-ChatbotPA has 747 clients across
10k samples, roughly thirteen preference pairs per client, far below what
a personal adapter needs. And no dataset in the suite contains an agent
proposal that a user then revised: Fed-WildChat is human-to-chatbot
conversation, Fed-ChatbotPA is a preference between two model responses.
The training signal this project needs, an agent's proposed output paired
with one analyst's revision of it, per specialist, does not exist there.

Consequence: Pharos carries the headline result, so it is sized for
adapter training rather than for illustration.

## Pharos is a generator, not a corpus

The fixed, versioned artifacts are the world, the label assignment rules,
the task instances, and the plant registry. The interaction streams are
generated per experiment under a fixed seed, at whatever volume personal
adapter training requires. A static dump would either be too small to
train a personal adapter or too large to review, and a generator is the
only way to hold both reproducibility and volume.

Everything a run consumes is therefore reproducible from a seed plus a
manifest, and the manifest is what a paper cites.

## The label model

A product lattice, following
[FIDES](https://arxiv.org/abs/2505.23643)'s label-plus-type construction:

```text
label = (sensitivity, compartments, type)

sensitivity  : OPEN < INTERNAL < PROTECTED < RESTRICTED    total order
compartments : subset of {SENSOR, LIAISON, LEGAL, PARTNER} subset lattice
type         : ENUM | SCALAR | SPAN | FREETEXT             capacity class
```

`sensitivity` is a ladder. `compartments` is what makes this a lattice
test rather than a ladder test: two analysts at the same sensitivity can
still be unable to share, because neither compartment set contains the
other. An entry's label is the join of the labels of every object that
fed the turn.

`type` is the declassification lever, and it is the answer to **label
creep**, the named failure mode of conservative propagation. Without it,
the join drives every entry to `RESTRICTED` and nothing federates. With
it, a low-capacity output declassifies by rule: an `ENUM` verdict such as
a triage decision or a quality flag cannot carry an instance, a
`FREETEXT` output always can. This is the principled form of the split
table in the spec, which classifies by source category and therefore
cannot distinguish a public notice from a restricted report.

Every declassification is a named, logged, reviewable event. That is a
requirement carried over from the information-flow literature, not a
convenience, and it is what a release decision is recorded against.

## The world

A fictional multi-agency maritime watch. Analysts are watch officers at
regional maritime operations centers, working a stream of vessel reports,
sensor tracks, port authority notices, crew manifests, and open-source
shipping press.

The domain is chosen for four structural properties, not for flavor:

- **Compartments are native and genuinely cross-cutting.** A
  sensor-derived track (`SENSOR`), a liaison-provided tip (`LIAISON`), a
  detention record that carries prosecutorial restrictions (`LEGAL`), and
  a partner-nation report released under caveat (`PARTNER`) can all
  concern the same vessel while sitting in incomparable compartments. An
  officer cleared for `{SENSOR, LEGAL}` and one cleared for
  `{LIAISON, PARTNER}` share a sensitivity level and still cannot pool
  what they know. This is the structure the lattice test needs and the one
  a single-department world cannot produce.
- **Sensitivity levels are native.** Open-source press through restricted
  reporting is the ordinary spread of the domain.
- **Heterogeneity falls out of geography.** Each center sees a different
  traffic mix, so client non-IID is a property of the world rather than a
  partitioning decision imposed on it.
- **Craft and style separate cleanly.** Craft is what makes a track
  significant and how a watch report is structured, shared across the
  fleet. Style is which operators and regions an officer prioritizes and
  their reporting voice, personal to them. The semantic-split experiment
  depends on that separation being real in the data.

Entirely fictional, so there is no licensing story and no real-world
sensitivity.

### Why "Pharos"

The lighthouse at Alexandria: a watch station whose entire function was
seeing what was coming, and reporting it to whoever needed to know.

## The generator

Configuration-driven rather than prompt-by-prompt, following
[DataMorgana](https://arxiv.org/abs/2501.12789)'s shape: the operator
declares report types, source channels, and officer voices, and the
generator composes across them. Diversity is forced at generation time
rather than filtered afterward, because uncontrolled generation is
monotonous and biased in ways that create exactly the surface regularities
the shortcut gate exists to catch. Crossing a single underlying event
across report type, source channel, and voice is the same technique that
held duplicate content under 1% in large synthetic corpora.

Three axes are crossed for every generated object:

- **Report type** — vessel report, sensor track, port notice, crew
  manifest, open-source press item.
- **Source channel** — which compartment the object lands in, and
  therefore what its label carries.
- **Officer voice** — the reporting register of the center that produced
  it, which is what gives the personal adapter something to learn.

The background stream and the plants come from the same generator with the
same axis crossing. Only the semantic property under test differs. That is
what makes the shortcut gate passable rather than a hurdle to be tuned
around.

## Task instances and ground truth

Ground truth is injected and registered, following the inject-then-score
pattern rather than post-hoc annotation.

| Specialist | Injected truth | Scored on |
| --- | --- | --- |
| Triage | Significant events seeded across several reports | Detection F1 against the plant registry |
| Retrieval | Known related-report sets per vessel and operator | Recall at k over the known set |
| Summarization | Required facts per vessel-activity window | Fact coverage and contradiction rate |
| Drafting | Required elements per watch-report template | Element presence and citation validity |

The plant registry is the authority for every score, and it is never
reachable from the environment the agents run in.

## The shortcut gate

Planted ground truth invites agents to learn the artifact of insertion
rather than the property under test. For a federated fleet the
consequence is worse than a single inflated score: **the shared adapter
federates the shortcut across every deployment**, so convergence looks
healthy while the fleet has learned an insertion tell.

Pharos is therefore unusable until it passes a surface-only probe. A
classifier given only non-semantic features, report length, timestamp
regularity, sender, formatting, field presence, must score **AUC between
0.45 and 0.55** on plant detection: at chance, with the band stated so the
gate is a pass/fail rather than a judgement call. Plants are generated by
the same generator as the background stream and differ only in the
semantic property being tested.

The probe result ships in the manifest for every corpus version. A
version that has not passed it is not a corpus.

## Canaries and the extraction claim

Canaries, not corpus realism, carry the extraction claim, because an
LLM-generated corpus sits at maximum pretraining overlap by construction
and would understate risk. That makes canary design load-bearing: audit
outcomes depend as much on canary construction as on the attack, and the
governing tradeoff is signal strength against naturalness, since an
unnatural canary measures a risk no real record poses.

Construction follows [The Canary's
Echo](https://arxiv.org/abs/2502.14921): an **in-distribution prefix** of
controlled length, paired with an **out-of-distribution suffix** generated
by a pretrained model at a tuned sampling temperature to hit a target
perplexity. Insertion count is a declared parameter in the manifest, not
an implementation detail, since exposure is meaningless without it.

**Reporting is multi-probe, and this is not optional.** In a LoRA-tuned
testbed, a single fixed prefix-window probe produces false negatives when
the secret falls outside the window, false positives where roughly 99% of
the probe's movement sits on non-secret preamble, and outright ambiguous
verdicts ([Fan et al. 2026](https://arxiv.org/abs/2606.31168)). Since this
project's entire privacy story runs through LoRA adapters, a single probe
would let us conclude whatever we hoped. Every extraction audit therefore
reports four things together:

1. Full-span secret negative log-likelihood.
2. Span-localized decomposition, so movement is attributed to the secret
   rather than its preamble.
3. Behavioral exact-recall at k >= 4.
4. Decoy probes, to substantiate any claim that a signal is
   secret-specific.

A round that reports one of these has not audited anything.

## Interaction streams

Simulated analysts produce the accept, revise, and reject signal. Three
requirements, each from a measured result rather than a preference:

- **Evolved persona policies, not hand-authored personas.** LLM user
  simulators inherit their base model's behavior, cooperative and
  homogeneous, so agents that look strong in simulation fail on the
  diverse patterns of real users
  ([Chopra et al. 2026](https://arxiv.org/abs/2605.12894)). Persona
  Policies casts persona generation as evolutionary program search over a
  generator scored on human-likeness plus behavioral coverage, and
  reaches 80.4% blinded human-likeness, close to real traces and nearly
  twice baseline simulators. This matters more here than for a capability
  benchmark: the personal adapter's whole job is to learn one analyst's
  idiosyncrasy, so homogeneous simulators leave nothing for it to learn
  and the personalization ablation separates noise.
- **Ensemble, not a single simulator.** Across 24 simulators most behave
  alike, and combining behaviorally complementary simulators lands closer
  to real users than any one of them
  ([Mehri et al. 2026](https://arxiv.org/abs/2605.07847)).
- **Report the gap honestly, in two parts.** The measurement is: extract a
  behavior representation per interaction, quantize by clustering, compute
  divergence. It requires a real reference, and Pharos has none, because
  there are no real watch officers in a fictional world. Pretending
  otherwise would make the number meaningless. So the claim splits:
  **in-domain, report inter-simulator divergence** across the ensemble,
  which needs no real reference and is what justifies ensembling at all;
  **out-of-domain, validate the pipeline** by running the same
  persona-policy search against Fed-WildChat, which does contain real
  human traces, and report simulated-to-real divergence there. The
  honest statement is that the *method* is validated against real humans
  in another domain and the *population* is only validated for internal
  diversity here. That is a limitation of any fictional world, and it
  belongs in the paper rather than in a footnote.

Deterministic scripted policies remain, for ablations that need exact
repeatability. They are a control, not the population.

## Two heterogeneity axes

The spec currently constructs non-IID from persona variation alone.
Pharos adds a second, independent axis:

- **Data axis** — regional traffic mix, which vessels and operators a
  center sees at all.
- **Persona axis** — how that center's officer works, what they
  prioritize, how they revise.

Crossing them separates two effects the single-axis design conflates:
adaptation to different *data* and adaptation to a different *analyst*.
The split claim is specifically about the second.

## Validity discipline

Built and reported against the [Agentic Benchmark
Checklist](https://arxiv.org/abs/2507.02825), whose survey found task and
reward design flaws mis-estimating agent performance by up to 100% in
relative terms. The checks that bind here:

- **Task validity** — a task is solvable if and only if the agent has the
  target capability. The shortcut gate above is this check made concrete.
- **Outcome validity** — the scorer indicates task success correctly.
  Scorers are exercised against adversarial inputs, empty strings,
  injected delimiters, unicode that normalizes unexpectedly, before use.
- **Judge reproducibility** — the LLM judges used for summarization and
  drafting quality are themselves benchmarked, with seeds and rubrics
  versioned in the manifest.
- **Process alongside outcome** — per-specialist process metrics are
  reported next to end-task quality, so a fleet that reaches the right
  answer the wrong way is visible.

Pharos also carries governance claims, which are security evaluations
rather than capability benchmarks, and those fail differently: benchmark
vulnerabilities, temporal staleness, and runtime uncertainty
([Abdelnabi et al. 2026](https://arxiv.org/abs/2605.22568)). Release-gate
and label-creep cases are versioned with the threat they encode, and are
expected to be refreshed rather than frozen.

## Evaluation changes this forces upstream

Two corrections to *Evaluation* in the spec, both from measured results:

- **Stratify privacy by distribution overlap, not by ε alone.** Practical
  privacy risk rises the closer adaptation data sits to the pretraining
  distribution, and theoretical DP guarantees do not translate to
  empirical protection under that overlap
  ([Marek et al., ICLR 2026](https://arxiv.org/abs/2606.09401)). An ε
  sweep alone measures the wrong variable. Report ε crossed with overlap,
  and note that LLM-generated corpora sit at maximum overlap by
  construction, which is why canaries carry the extraction claim.
- **Replace hand-authored personas** in *Simulated analysts* with evolved
  persona policies plus the ensemble and divergence reporting above.

## Build order

This is more than one implementation plan, and pretending otherwise would
produce a plan nobody can execute. It decomposes into three, in dependency
order, each shippable and useful on its own:

1. **World and labels.** The document generator, the label assigner over
   the product lattice, and the manifest. Ends with a corpus that passes
   the shortcut gate. Nothing downstream is trustworthy until this does.
2. **Tasks and scorers.** Task instances, the plant registry, and the four
   specialist scorers, with the adversarial-input pass over each scorer.
   Ends with a scored baseline against a fixed agent.
3. **Simulated analysts.** Persona-policy search, the simulator ensemble,
   and divergence reporting. Ends with accept/revise/reject streams at
   training volume, and a published divergence figure.

Adapter training volume is set by measurement in step 3 rather than
guessed here: generate until personal-adapter validation loss stops
improving, and record the volume that took.

## What Pharos does not do

- It does not host the fleet. It is data plus a generator plus a scorer.
- It does not carry a federation mechanism claim on its own.
- It does not model a real program, organization, or vessel.
- It does not ship agents, adapters, or aggregation code.

## References

- [FedLLM-Bench: Realistic Benchmarks for Federated Learning of Large Language Models](https://arxiv.org/abs/2406.04845) — NeurIPS 2024 Datasets and Benchmarks
- [Securing AI Agents with Information-Flow Control (FIDES)](https://arxiv.org/abs/2505.23643)
- [Beyond Cooperative Simulators: Generating Realistic User Personas](https://arxiv.org/abs/2605.12894)
- [Measuring and Mitigating the Distributional Gap Between Real and Simulated User Behaviors](https://arxiv.org/abs/2605.07847)
- [Establishing Best Practices for Building Rigorous Agentic Benchmarks](https://arxiv.org/abs/2507.02825)
- [Measuring Security Without Fooling Ourselves: Why Benchmarking Agents Is Hard](https://arxiv.org/abs/2605.22568)
- [Benchmarking Empirical Privacy Protection for Adaptations of Large Language Models](https://arxiv.org/abs/2606.09401) — ICLR 2026
- [Towards the Next Frontier of LLMs, Training on Private Data](https://arxiv.org/abs/2605.13936) — cross-domain federated fine-tuning comparator
- [Generating Diverse Q&A Benchmarks for RAG Evaluation with DataMorgana](https://arxiv.org/abs/2501.12789) — configuration-driven generation
- [The Canary's Echo: Auditing Privacy Risks of LLM-Generated Synthetic Text](https://arxiv.org/abs/2502.14921) — canary construction
- [Probe Choice Changes Canary-Memorization Verdicts](https://arxiv.org/abs/2606.31168) — multi-probe reporting in a LoRA-tuned testbed
- [On the Diversity of Synthetic Data and its Impact on Training Large Language Models](https://arxiv.org/abs/2410.15226) — diversity measurement
