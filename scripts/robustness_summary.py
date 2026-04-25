"""Aggregate robustness-run statistics across seeds.

Reads outputs/data/robustness/{variant}_seed*.json files, recomputes leaderboard
and feature marginals per run, and prints a markdown summary. Also writes a
combined JSON to outputs/data/robustness/{variant}_summary.json.

Usage:
    python scripts/robustness_summary.py [--variants standard antichess]
                                          [--top-k 3]
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.feature_subset_agent import FeatureSubsetAgent
from analysis.feature_marginals import compute_feature_marginals
from simulation.game import GameResult
from tournament.leaderboard import compute_leaderboard

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "outputs", "data", "robustness")


def _load_results(path: str) -> list[GameResult]:
    """Decode JSON back into GameResult objects (mirrors tournament.results_io)."""
    with open(path) as f:
        data = json.load(f)
    out: list[GameResult] = []
    for d in data:
        out.append(GameResult(
            white_agent=d["white_agent"],
            black_agent=d["black_agent"],
            winner=d["winner"],
            moves=d["moves"],
            termination_reason=d.get("termination_reason"),
            white_avg_nodes=d.get("white_avg_nodes", 0.0),
            black_avg_nodes=d.get("black_avg_nodes", 0.0),
            white_avg_time=d.get("white_avg_time", 0.0),
            black_avg_time=d.get("black_avg_time", 0.0),
            move_list=d.get("move_list", []),
        ))
    return out


def _agents_from_results(results: list[GameResult]) -> list[FeatureSubsetAgent]:
    names: set[str] = set()
    for r in results:
        names.add(r.white_agent)
        names.add(r.black_agent)
    out = []
    for name in sorted(names):
        feats = tuple(name.replace("Agent_", "").split("__"))
        out.append(FeatureSubsetAgent(
            name=name, features=feats,
            weights={f: 1.0 / len(feats) for f in feats},
        ))
    return out


def _kendall_tau(rank_a: list[str], rank_b: list[str]) -> float:
    """Kendall's tau between two rankings (lists of agent names in order)."""
    common = list(set(rank_a) & set(rank_b))
    n = len(common)
    if n < 2:
        return 1.0
    pos_a = {x: i for i, x in enumerate(rank_a)}
    pos_b = {x: i for i, x in enumerate(rank_b)}
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            x, y = common[i], common[j]
            sa = pos_a[x] - pos_a[y]
            sb = pos_b[x] - pos_b[y]
            if sa * sb > 0:
                concordant += 1
            elif sa * sb < 0:
                discordant += 1
    total = n * (n - 1) / 2
    return (concordant - discordant) / total


def _summarize_variant(variant: str, top_k: int) -> dict | None:
    paths = sorted(glob.glob(os.path.join(OUT_DIR, f"{variant}_seed*.json")))
    if not paths:
        return None

    runs = []
    for p in paths:
        seed = int(re.search(r"seed(\d+)\.json$", p).group(1))
        results = _load_results(p)
        agents = _agents_from_results(results)
        feat_names = sorted({f for a in agents for f in a.features})
        lb = compute_leaderboard(results, agents)
        marginals = compute_feature_marginals(lb, feat_names)
        runs.append({
            "seed": seed,
            "path": p,
            "leaderboard": lb,
            "marginals": marginals,
            "ranking": [r.agent_name for r in lb],
        })

    n_runs = len(runs)

    # Top-1 winner frequency
    top1 = Counter(run["leaderboard"][0].agent_name for run in runs)

    # Top-k appearance rate
    topk_appear: Counter[str] = Counter()
    for run in runs:
        for r in run["leaderboard"][:top_k]:
            topk_appear[r.agent_name] += 1

    # Per-feature marginal stats
    feat_names = sorted({m.feature for run in runs for m in run["marginals"]})
    per_feat: dict[str, dict] = {}
    for f in feat_names:
        vals = [m.marginal for run in runs for m in run["marginals"] if m.feature == f]
        positive = sum(1 for v in vals if v > 0)
        per_feat[f] = {
            "mean": statistics.mean(vals),
            "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            "positive_count": positive,
            "n_runs": len(vals),
        }

    # Mean Kendall tau across all pairs of runs
    taus = []
    for i in range(n_runs):
        for j in range(i + 1, n_runs):
            taus.append(_kendall_tau(runs[i]["ranking"], runs[j]["ranking"]))
    mean_tau = statistics.mean(taus) if taus else 1.0

    return {
        "variant": variant,
        "n_runs": n_runs,
        "seeds": [run["seed"] for run in runs],
        "top1_frequency": top1.most_common(),
        "topk_appearance": topk_appear.most_common(),
        "per_feature": per_feat,
        "mean_kendall_tau": mean_tau,
        "top_k": top_k,
    }


def _print_markdown(summary: dict) -> None:
    v = summary["variant"]
    n = summary["n_runs"]
    print(f"## {v.upper()}  ({n} seeds: {summary['seeds']})")
    print()

    print(f"**Top-1 winner frequency**")
    for name, count in summary["top1_frequency"]:
        short = name.replace("Agent_", "").replace("__", " + ")
        pct = 100.0 * count / n
        print(f"  - `{short}`  →  **{count}/{n}** ({pct:.0f}%)")
    print()

    print(f"**Top-{summary['top_k']} appearance rate**")
    for name, count in summary["topk_appearance"][:8]:
        short = name.replace("Agent_", "").replace("__", " + ")
        print(f"  - `{short}`  →  {count}/{n}")
    print()

    print(f"**Feature marginal stability** (mean ± std, sign-positive count)")
    feats_sorted = sorted(summary["per_feature"].items(),
                          key=lambda kv: kv[1]["mean"], reverse=True)
    for f, st in feats_sorted:
        sign = f"{st['positive_count']}/{st['n_runs']} positive"
        print(f"  - {f:<22s}  {st['mean']:+.3f} ± {st['stdev']:.3f}   {sign}")
    print()

    tau = summary["mean_kendall_tau"]
    print(f"**Leaderboard rank stability**: mean Kendall τ = **{tau:+.3f}**  "
          f"(1.0 = identical rankings, 0 = uncorrelated, -1 = reversed)")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate robustness runs")
    parser.add_argument("--variants", nargs="+", default=["standard", "antichess"])
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    if not os.path.isdir(OUT_DIR):
        print(f"No robustness data found at {OUT_DIR}")
        print("Run scripts/robustness_test.py first.")
        return

    print(f"# Robustness summary  (data: {OUT_DIR})")
    print()

    for variant in args.variants:
        summary = _summarize_variant(variant, args.top_k)
        if summary is None:
            print(f"## {variant.upper()}  —  no seed runs found, skipping.")
            print()
            continue
        _print_markdown(summary)

        # Persist the JSON summary alongside the per-seed runs
        json_path = os.path.join(OUT_DIR, f"{variant}_summary.json")
        serializable = dict(summary)
        # Convert per_feature stats to plain dict (already JSON-safe)
        with open(json_path, "w") as f:
            json.dump(serializable, f, indent=2)
        print(f"_Summary JSON: `{json_path}`_")
        print()


if __name__ == "__main__":
    main()
