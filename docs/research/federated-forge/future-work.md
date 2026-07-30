# Federated Forge — deferred scope and future work

Scope carved out of the [design spec](./index.md) and the
[Pharos testbed spec](./pharos-testbed.md), with the reason for each cut
and where the work is expected to land. Deferred here means "not in the
flagship's critical path", never "abandoned".

Placement follows the papers-repo convention: manuscript lineage lives in
that repo's `LINEAGE.md`, and this file records *design* scope so a reader
of the spec can see why a mechanism the design clearly needs is not being
built alongside it.

## Deferred: gauge-fixed Byzantine defense

**What it is.** LoRA factorizations are not unique: `(A, B)` and
`(AR, R^-1 B)` encode the same update `ΔW = BA`. Distance-based defenses
computed on raw stacked factors can therefore assign different distances
to identical updates, so an honest client can be scored as an outlier for
a gauge choice rather than for its contribution. The fix is to compute
defenses over composed per-layer `ΔW`, or over an equivalent gauge-fixed
representation, at a cost of roughly one rank-r matmul per layer per
client.

**Why deferred.** It is a genuine, separable contribution about how robust
aggregation should be *computed*, and it stands on its own without any of
the personalization apparatus. Keeping it in the flagship dilutes a thesis
that is about a disclosure boundary, not about robust aggregation.

**Where it lands.** The velocity-fl systems paper (P1), which already
claims a Byzantine attack arena. That is the natural venue, and it needs
one framing constraint honored.

**Framing constraint, non-negotiable.** P1 is framed as systems and
reproducibility, never as a new anomaly-detection or malicious-client
algorithm, because that lane belongs to the lab's PID-MADE line. Gauge
fixing sits on the correct side of that boundary when it is presented as
what it actually is: **a correctness fix for how existing defenses are
computed over a non-unique representation.** It proposes no new detector
and no new trust score. Presenting it instead as an improved defense would
cross into the lab's lane, so the framing is load-bearing rather than
cosmetic. Any draft states the relationship explicitly and cites the lab
line.

**What the flagship still needs meanwhile.** The flagship reports
robustness under poisoning, so it uses a gauge-fixed defense as
*infrastructure* and cites the contribution rather than claiming it. The
flagship's own claim stays "the split survives poisoned clients", not
"here is a better defense".

## Deferred: online preference-learning algorithm comparison

**What it is.** A head-to-head of COPO, DICE, Uni-DPO, and vanilla
iterative DPO on the personal adapter, to establish which online
preference-learning method suits a continuously updated, single-analyst
adapter.

**Why deferred.** It is an alignment-methods question rather than a
federation or disclosure question. The flagship needs *one* method that
works, not a ranking of four, and the comparison's cost scales with the
number of specialists it has to run against.

**Where it lands.** Its own follow-on, most naturally as a lighter-lane
paper rather than part of P1 or the kourai paper, since neither covers
personalization methods. Until then the flagship fixes a single method,
records the choice, and cites the alternatives as unexplored.

## Retained deliberately: the corrected-LoRA aggregation family

Not deferred, and the decision to keep all three arms is deliberate rather
than indecision, so the spec should read that way.

Averaging the products `B·A` is not the product of the averaged factors,
so vanilla FedAvg over stacked LoRA matrices is simply incorrect. Three
corrections exist and they are not interchangeable here:

- **FedEx-LoRA** is exact, pushing residual error into the frozen base
  weights. That is precisely the arm with a setting-specific hazard: this
  design layers a *per-deployment personal adapter* on the same modules,
  and a residual folded into the shared frozen base can collide with it.
  Whether the exact method stays exact under heterogeneous personal
  adapters is an open question in the spec, not a settled result.
- **LoRA-FAIR** applies a server-side correction term, approximate but
  with no base-weight write, so it sidesteps that collision entirely.
- **Share-A-only** avoids the product problem by construction rather than
  correcting it, at the cost of federating less.

The three differ exactly along the axis this project introduces, namely
the presence of a private adapter on the same layers. Picking one from the
literature would be picking on evidence gathered in a setting that does
not have that adapter. Implementing all three and reporting which wins is
therefore a result about *this* architecture, cheap relative to its
value since the three share a harness, and the honest way to answer a
question the spec already raises.

## Deferred: label-lattice generalization beyond the maritime instantiation

Pharos instantiates one lattice: four sensitivity levels and four
compartments, chosen to exercise a subset lattice without making seed data
combinatorially unmanageable. Whether the governed-label mechanism holds
under deeper compartment nesting, originator-control style caveats that
constrain onward release rather than initial access, or a lattice supplied
by a real accreditation authority is untested and out of scope here.

## Not deferred, and not solved: release authority

Recorded here so it is not mistaken for deferred scope. The
differential-privacy-to-quantitative-information-flow bound gives a
defensible number for what a shared update can reveal. It does not supply
who authorizes release, at what threshold, or what happens when the bound
is exceeded. No accreditor treats an epsilon as a declassification
decision.

This does not block the research and it does block fielding. It stays
visible in the spec's open questions rather than being filed as future
work, because a reviewer who works on cross-domain solutions will ask
about it first.
