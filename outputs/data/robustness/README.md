# Robustness data

Per-seed tournament runs for measuring leaderboard stability under game-tiebreak
randomness. Same agent population (agent-gen seed=42) across all runs; only the
tournament-level game seed varies.

## Files

- `{variant}_seed{N}.json` — one tournament's raw `GameResult` list at seed N.
- `{variant}_summary.json` — aggregated stats across all seeds for a variant
  (top-1 frequency, top-K appearance, feature marginal stability, Kendall τ).

## Reproducing

```bash
# Run 5 seeds for standard + antichess (defaults: agents=20, depth=2)
python scripts/robustness_test.py --variants standard antichess --seeds 5

# Aggregate + print markdown summary
python scripts/robustness_summary.py --variants standard antichess
```

## Interpretation

- **Top-1 winner frequency**: how often each agent wins outright.
- **Top-K appearance rate**: how often an agent lands in top-K — looser than
  top-1 and usually a more stable signal.
- **Feature marginal stability**: per-feature mean ± std of marginal across
  runs, plus sign-stability count (e.g., "5/5 positive" = always helpful).
- **Mean Kendall τ**: pairwise rank correlation of full leaderboards.
  1.0 = identical rankings, 0 = uncorrelated, negative = anti-correlated.

This data is **not** surfaced in the web app. The web app reads
`outputs/data/tournament_results_{variant}.json` (canonical seed=42 run).
