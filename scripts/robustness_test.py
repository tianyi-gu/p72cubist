"""Robustness testing: run N tournaments per variant with different game seeds.

Same agent population (seed=42 for agent generation) — only the tournament-level
game seed varies. This isolates "how stable is the leaderboard under game-tiebreak
randomness?" from agent-population effects.

Usage:
    python scripts/robustness_test.py [--variants standard antichess]
                                       [--seeds 5] [--agents 20]
                                       [--depth 2] [--workers N]
                                       [--start-seed 42]

Output: outputs/data/robustness/{variant}_seed{N}.json — one file per run.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.generate_agents import generate_feature_subset_agents
from tournament.round_robin import run_round_robin
from scripts.precompute_tournaments import VARIANT_FEATURES

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "outputs", "data", "robustness")


def _run_one_seed(variant: str, features: list[str], max_moves: int,
                  max_agents: int, depth: int, tournament_seed: int,
                  workers: int) -> tuple[int, float]:
    """Run one tournament at a given seed; save results JSON. Returns (n_games, elapsed)."""
    # Agent population fixed across seeds (agent-gen seed=42 always).
    agents = generate_feature_subset_agents(features, max_agents=max_agents, seed=42)

    t0 = time.time()
    results = run_round_robin(
        agents, variant, depth=depth, max_moves=max_moves,
        seed=tournament_seed, workers=workers,
    )
    elapsed = time.time() - t0

    out = [
        {
            "white_agent": r.white_agent,
            "black_agent": r.black_agent,
            "winner": r.winner,
            "moves": r.moves,
            "termination_reason": r.termination_reason,
            "white_avg_nodes": r.white_avg_nodes,
            "black_avg_nodes": r.black_avg_nodes,
            "white_avg_time": r.white_avg_time,
            "black_avg_time": r.black_avg_time,
            "move_list": getattr(r, "move_list", []),
        }
        for r in results
    ]
    path = os.path.join(OUT_DIR, f"{variant}_seed{tournament_seed}.json")
    with open(path, "w") as f:
        json.dump(out, f)
    return len(results), elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Robustness: N seeds per variant")
    parser.add_argument("--variants", nargs="+", default=["standard", "antichess"])
    parser.add_argument("--seeds", type=int, default=5,
                        help="Number of seeds (default: 5)")
    parser.add_argument("--start-seed", type=int, default=42)
    parser.add_argument("--agents", type=int, default=20)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--workers", type=int, default=multiprocessing.cpu_count())
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    seeds = list(range(args.start_seed, args.start_seed + args.seeds))
    print(f"Robustness sweep: variants={args.variants} seeds={seeds} "
          f"agents={args.agents} depth={args.depth} workers={args.workers}")
    print()

    grand_t0 = time.time()
    for variant in args.variants:
        if variant not in VARIANT_FEATURES:
            print(f"  [skip] unknown variant '{variant}'")
            continue
        features, max_moves = VARIANT_FEATURES[variant]
        print(f"=== {variant.upper()} ===")
        for seed in seeds:
            n, el = _run_one_seed(variant, features, max_moves, args.agents,
                                  args.depth, seed, args.workers)
            print(f"  seed={seed}: {n} games in {el:.1f}s")
        print()

    print(f"Total: {time.time() - grand_t0:.1f}s")
    print(f"Files written to: {OUT_DIR}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
