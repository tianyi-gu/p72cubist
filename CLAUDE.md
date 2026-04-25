# EngineLab

Interpretable strategy-discovery system for chess variants via exhaustive
feature-subset testing with alpha-beta engines.

## Quick Reference

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run all tests
pytest

# Run specific area tests
pytest tests/test_board.py tests/test_move_generation.py tests/test_atomic.py  # Area 1
pytest tests/test_features.py                                                   # Area 2
pytest tests/test_agents.py tests/test_alpha_beta.py                           # Area 3
pytest tests/test_tournament.py                                                 # Area 4
pytest tests/test_analysis.py                                                   # Area 5

# Run the full pipeline
python main.py full-pipeline --variant atomic --depth 2 --max-moves 80
```

## Conventions (MUST follow)

- **Pieces:** FEN chars. Uppercase = white (`P N B R Q K`), lowercase = black (`p n b r q k`), empty = `None`
- **Colors:** Always `"w"` or `"b"`. Never `"white"` / `"black"` in data structures.
- **Coordinates:** `grid[row][col]`. Row 0 = rank 1 (white side). Col 0 = file a.
- **Board.copy():** Must deep-copy. Modifying copy must not affect original.
- **Agent names:** `Agent_{feat1}__{feat2}` -- double underscore separator, features sorted alphabetically.

## Architecture

Five development areas, each with dedicated files:

| Area | Scope                      | Key files                              |
|------|----------------------------|----------------------------------------|
| 1    | Core chess + Atomic rules  | `core/`, `variants/`, `tests/test_board.py` etc. |
| 2    | Features + registry        | `features/`, `tests/test_features.py`  |
| 3    | Agents + evaluation + search | `agents/`, `search/`, `tests/test_agents.py` etc. |
| 4    | Simulation + tournament    | `simulation/`, `tournament/`, `tests/test_tournament.py` |
| 5    | Analysis + reports + CLI   | `analysis/`, `reports/`, `main.py`, `tests/test_analysis.py` |

## Key Rules

- **Do not edit files outside your area.** See `docs/agent_definitions.md` for ownership.
- **Do not change shared interfaces** without updating `docs/interfaces.md` first.
- **No castling, en passant, or underpromotion** in MVP.
- **Self-preservation rule is REQUIRED:** Filter out captures that would explode own king.
- Read `Instructions.MD` for the full PRD. Read `docs/interfaces.md` for exact signatures.
- Read `docs/harness_engineering.md` for agent operation best practices and validation protocol.

## Determinism

All output must be deterministic given the same seed. Move generation must iterate
pieces in fixed order (row 0-7, col 0-7). Use `random.Random(seed)` (local instance),
never `random.seed()` on the global RNG. Run the pipeline twice with the same seed
and diff the outputs to verify.
