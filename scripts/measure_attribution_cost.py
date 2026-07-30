#!/usr/bin/env python3
"""Measure what it costs to compute a governed label for one ledger entry.

Produces the attribution-cost figure cited in
`docs/research/federated-forge/index.md`: the ratio of a ContextCite-style
ablation budget to the agent turn it explains.

The question this answers is whether the shared/personal split can be decided
from data provenance without making the analyst wait. Attributing an output to
the retrieved objects that fed it is the expensive half of that decision, so
the ratio decides whether attribution runs inline or deferred.

Method. One baseline turn generates a summary over N retrieved sources. Then K
ablation passes each score the *fixed* baseline response under a randomly
masked subset of those sources (`num_predict=1`), so what is timed is prefill,
which is what a real scoring pass costs. Masks are randomized so the server's
prompt cache cannot flatter the result, and the baseline is warmed with a
different prompt so its own prefill is not already cached.

Reports median and p90 per-pass latency, flags stalls separately rather than
averaging them into the headline, and prints the ratio both ways.

Requires a running Ollama with the target model pulled. Run from the repo root:

    uv run python scripts/measure_attribution_cost.py
    uv run python scripts/measure_attribution_cost.py --sources 20 --ablations 64
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_ABLATIONS = 32  # ContextCite's typical budget
STALL_FACTOR = 3.0  # a pass slower than this multiple of the median is a stall
REQUEST_TIMEOUT_S = 900

SYSTEM = "You are a maritime watch officer's summarization assistant."

INSTRUCTION = (
    "Using only the reports above, summarise what is known about the motor vessel "
    "Kestrel Dawn during this watch window. State each fact and the report it came "
    "from. Do not speculate beyond the reports."
)

# Representative retrieved reports for a Pharos-shaped turn: mixed source
# channels, each roughly 110-140 tokens, one underlying event spread across
# several of them so attribution has something real to resolve.
SOURCES: tuple[str, ...] = (
    "VESSEL REPORT 4471-A (SENSOR). Motor vessel Kestrel Dawn, IMO 9284471, bulk carrier, "
    "flag Panama. Automatic identification system track shows departure from berth 12 at "
    "0412Z, transiting outbound channel at 11.4 knots, draft reported 9.2 metres against a "
    "laden declaration of 12.1 metres. Course alteration to 187 degrees at 0451Z placed the "
    "vessel outside the declared routing for its filed destination. No pilot aboard on "
    "departure despite compulsory pilotage in this approach. Operator of record is Halcyon "
    "Shipping Management, registered Limassol.",
    "PORT NOTICE 2210 (OPEN). Port authority bulletin: berth 12 and berth 13 closed to "
    "commercial traffic 0600Z to 1800Z for crane maintenance. Vessels with scheduled loading "
    "windows in this period are directed to anchorage Delta and should expect a minimum eight "
    "hour delay. Agents are reminded that shifting berths requires 24 hours notice under local "
    "rule 14. Two vessels have already been reassigned. Weather is forecast fair with "
    "visibility above eight nautical miles.",
    "CREW MANIFEST 8813 (LEGAL). Motor vessel Kestrel Dawn, crew of nineteen. Master listed as "
    "R. Ibarra, holding a certificate issued by Panama, first issued 2019, endorsement current. "
    "Chief engineer position shows a substitution filed 36 hours before departure, replacing "
    "the previously declared engineer with an individual whose certificate number does not "
    "resolve against the issuing registry. Fourteen crew hold the same recruitment agency "
    "reference. Two crew are recorded as joining at the previous port without immigration "
    "clearance entries.",
    "SENSOR TRACK 5502 (SENSOR). Coastal radar holds an unlit contact 2.1 nautical miles "
    "north-northeast of the Kestrel Dawn track between 0455Z and 0523Z, closing to 340 metres "
    "at nearest approach before separating on a reciprocal heading. The contact did not "
    "transmit an automatic identification system signal at any point. Radar cross section is "
    "consistent with a small craft of eight to twelve metres. Sea state was calm. The contact's "
    "track originates from and returns toward the eastern shoal approaches, which have no "
    "lawful berthing.",
    "PRESS ITEM 331 (OPEN). Regional shipping trade publication reports that Halcyon Shipping "
    "Management has been in commercial dispute with two charterers over demurrage claims on "
    "three vessels during the current quarter. The article notes the operator has recently "
    "reflagged four vessels and quotes an unnamed broker describing the fleet's scheduling as "
    "increasingly irregular. No regulatory action is mentioned. The article carries a "
    "photograph of an unrelated vessel at an unidentified berth.",
    "LIAISON TIP 0097 (LIAISON). Partner service advises that a vessel matching the Kestrel "
    "Dawn profile was observed conducting an unscheduled ship-to-ship transfer in international "
    "water approximately 140 nautical miles from this port within the last fourteen days. The "
    "reporting is characterised as single source and uncorroborated. No imagery accompanies the "
    "report. The partner requests that any derived reporting be held to originator control and "
    "not further disseminated without consultation.",
    "VESSEL REPORT 4402-B (SENSOR). Motor vessel Northern Aster, IMO 9331882, general cargo, "
    "flag Liberia. Routine outbound transit, pilot aboard, draft consistent with declaration, "
    "no course anomalies. Departure 0338Z at 9.1 knots on filed routing to declared "
    "destination. Operator Meridian Lines, no adverse history in this port. Included for "
    "background traffic comparison during the same watch window.",
    "PORT NOTICE 2211 (OPEN). Advisory: the eastern shoal approaches remain closed to all "
    "traffic following the survey of 12 June. Depths in the area are unreliable and no berthing "
    "is authorised. Masters are reminded that transit of the closed area is a reportable "
    "violation. Two small craft were observed in the area during the previous month and "
    "referred to enforcement.",
    "DETENTION RECORD 1180 (LEGAL). Port state control inspection history for Halcyon Shipping "
    "Management vessels: four inspections in the preceding eighteen months, two resulting in "
    "deficiencies related to certificate documentation for engineering officers, one detention "
    "lifted after 62 hours. This record is subject to prosecutorial restriction and may not be "
    "quoted in disseminated product without legal review. Two of the four inspections concerned "
    "vessels since reflagged.",
    "PARTNER REPORT 0451 (PARTNER). Partner-nation maritime authority reports increased "
    "small-craft activity along the eastern shoal approaches during hours of darkness across "
    "the past three weeks, assessed by the partner as probable unregulated transfer activity. "
    "Released under caveat: partner-nation eyes only unless upgraded by the originator. The "
    "partner does not associate the activity with any named vessel or operator.",
)


def call(endpoint: str, model: str, prompt: str, num_predict: int) -> dict[str, object]:
    """One generate call, returning Ollama's response including timing fields."""
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": num_predict, "temperature": 0.0, "seed": 7},
        }
    ).encode()
    request = urllib.request.Request(  # noqa: S310 -- fixed localhost Ollama endpoint, not user input
        endpoint, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as fh:  # noqa: S310 -- same
        return json.load(fh)


def build_prompt(sources: tuple[str, ...] | list[str], suffix: str = "") -> str:
    """System preamble, the retrieved sources, the instruction, then any suffix."""
    return f"{SYSTEM}\n\n{'\n\n'.join(sources)}\n\n{INSTRUCTION}\n\n{suffix}"


def to_ms(nanoseconds: object) -> float:
    return round(float(nanoseconds or 0) / 1e6, 1)


def measure(endpoint: str, model: str, n_sources: int, k_ablations: int, seed: int) -> dict:
    """Run the baseline turn and the ablation budget, returning the measurement."""
    sources = SOURCES[:n_sources]
    random.seed(seed)

    # Warm on a DIFFERENT prompt, so the baseline turn's own prefill is not cached.
    print(f"warming {model} (result discarded)...")
    call(endpoint, model, "Summarise: the harbour was quiet overnight.", 8)

    print(f"baseline turn over {len(sources)} sources...")
    turn = call(endpoint, model, build_prompt(sources), 320)
    response = str(turn.get("response", ""))
    turn_total_ms = to_ms(turn.get("total_duration"))
    print(
        f"  ctx={turn.get('prompt_eval_count')} tok  "
        f"prefill={to_ms(turn.get('prompt_eval_duration'))} ms  "
        f"gen={turn.get('eval_count')} tok / {to_ms(turn.get('eval_duration'))} ms  "
        f"TOTAL={turn_total_ms} ms"
    )

    print(f"{k_ablations} ablation scoring passes...")
    per_pass_ms: list[float] = []
    pass_tokens: list[int] = []
    for i in range(k_ablations):
        # Each source in or out at p=0.5, ContextCite-style. Seeded stdlib PRNG
        # is the point here: the mask sequence has to be reproducible.
        kept = [s for s in sources if random.random() < 0.5] or [sources[0]]  # noqa: S311
        # Score the FIXED baseline response under the ablated context.
        result = call(endpoint, model, build_prompt(kept, suffix=response), 1)
        per_pass_ms.append(to_ms(result.get("prompt_eval_duration")))
        pass_tokens.append(int(result.get("prompt_eval_count") or 0))
        if (i + 1) % 8 == 0:
            print(f"  {i + 1}/{k_ablations}, median so far {statistics.median(per_pass_ms):.0f} ms")

    median_ms = statistics.median(per_pass_ms)
    stalls = [x for x in per_pass_ms if x > STALL_FACTOR * median_ms]
    clean = [x for x in per_pass_ms if x <= STALL_FACTOR * median_ms]
    ordered = sorted(per_pass_ms)

    return {
        "model": model,
        "n_sources": len(sources),
        "k_ablations": k_ablations,
        "seed": seed,
        "turn_ctx_tokens": turn.get("prompt_eval_count"),
        "turn_gen_tokens": turn.get("eval_count"),
        "turn_prefill_ms": to_ms(turn.get("prompt_eval_duration")),
        "turn_total_ms": turn_total_ms,
        "pass_tokens_median": int(statistics.median(pass_tokens)),
        "pass_ms_median": round(median_ms, 1),
        "pass_ms_p90": round(ordered[int(len(ordered) * 0.9)], 1),
        "pass_ms_max": round(ordered[-1], 1),
        "stall_count": len(stalls),
        "attribution_total_ms": round(sum(per_pass_ms), 1),
        "attribution_stall_free_ms": round(sum(clean) * k_ablations / len(clean), 1),
        "ratio_observed": round(sum(per_pass_ms) / turn_total_ms, 2),
        "ratio_stall_free": round(sum(clean) * k_ablations / len(clean) / turn_total_ms, 2),
        "per_pass_ms": per_pass_ms,
    }


def report(m: dict) -> None:
    """Print the headline figures, keeping stalls out of the reported ratio."""
    print()
    print("=" * 66)
    print(f"model                     {m['model']}")
    print(f"sources / ablations       {m['n_sources']} / {m['k_ablations']}")
    print(f"turn context tokens       {m['turn_ctx_tokens']}")
    print(f"BASELINE turn             {m['turn_total_ms']} ms")
    print(
        f"per-pass latency          p50 {m['pass_ms_median']}  "
        f"p90 {m['pass_ms_p90']}  max {m['pass_ms_max']} ms"
    )
    print(f"stalls (>{STALL_FACTOR:g}x median)      {m['stall_count']}")
    print(f"ATTRIBUTION total         {m['attribution_total_ms']} ms")
    print(f"RATIO observed            {m['ratio_observed']}x")
    print(f"RATIO stall-free          {m['ratio_stall_free']}x   <- report this one")
    print("=" * 66)
    print("Inline, this latency is added to every turn. Deferred, it is background")
    print("work that must finish before the local trainer consumes the entry.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sources", type=int, default=len(SOURCES))
    parser.add_argument("--ablations", type=int, default=DEFAULT_ABLATIONS)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--out", type=Path, help="Write the full measurement as JSON here.")
    args = parser.parse_args()

    if not 1 <= args.sources <= len(SOURCES):
        parser.error(f"--sources must be between 1 and {len(SOURCES)}")

    measurement = measure(args.endpoint, args.model, args.sources, args.ablations, args.seed)
    report(measurement)

    if args.out:
        args.out.write_text(json.dumps(measurement, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
