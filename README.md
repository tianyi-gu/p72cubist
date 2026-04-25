# EngineLab

EngineLab is a Python chess-variant experimentation framework for testing which evaluation features perform well under different rule sets. It generates feature-subset agents, runs them through round-robin self-play tournaments, ranks the agents, analyzes marginal feature contribution and pairwise feature synergy, and exposes the same workflow through a CLI, Streamlit UI, and FastAPI endpoint.

This repository is not a neural-network chess engine, not a Stockfish wrapper, and not an Elo-calibrated playing engine. The core idea is controlled feature discovery: build many lightweight agents from different combinations of handcrafted evaluation features, let them play under variant-specific rules, then inspect which features or feature pairs correlate with stronger tournament performance.

## What the system does

At a high level, the project has five layers:

1. **Chess state and rules engine**: internal board representation, move model, FEN conversion, move generation, legal move filtering, move application, castling, en passant, promotion, check detection, and variant dispatch.
2. **Evaluation features**: handcrafted scoring functions such as material, mobility, king safety, center control, pawn structure, capture threats, and variant-targeted features such as negative material and king proximity.
3. **Agents and search**: feature-subset agents use equal-weighted feature combinations and select moves through a depth-limited alpha-beta negamax engine.
4. **Tournament and analysis pipeline**: round-robin self-play, leaderboard scoring, feature marginal analysis, pairwise synergy analysis, JSON/CSV export, and Markdown report generation.
5. **Interfaces**: Typer CLI, Streamlit dashboard, FastAPI server with Server-Sent Events, and a browser-based drag-and-drop chess board component.

## Repository layout

```text
.
├── agents/                 # Feature-subset agent model, generation, and evaluation wrapper
├── analysis/               # Feature marginal and pairwise synergy analysis
├── api/                    # FastAPI server for feature/variant discovery and streamed tournaments
├── core/                   # Board, move, coordinate, move generation, and move application logic
├── docs/                   # Design notes, interfaces, UI specs, and workflow documentation
├── features/               # Registered handcrafted evaluation features
├── reports/                # Markdown report generator
├── scripts/                # Precomputation and robustness scripts
├── search/                 # Alpha-beta negamax search engine
├── simulation/             # Game loop and random-agent support
├── tests/                  # Unit and integration-style test suite
├── tournament/             # Round-robin execution, leaderboard computation, result I/O
├── ui/                     # Streamlit application and chess board rendering/play support
├── variants/               # Standard chess and supported variant rule implementations
├── export_data.py          # Converts tournament JSON into analysis CSV/JSON artifacts
├── main.py                 # CLI entry point
├── requirements.txt        # Python dependencies
└── run_local.sh            # Convenience launcher for local UI/API workflows
```

## Core architecture

### Board model

The internal board is defined in `core/board.py`. It stores:

- `grid`: 8x8 piece array using uppercase pieces for White and lowercase pieces for Black.
- `side_to_move`: `w` or `b`.
- `winner`: `w`, `b`, `draw`, or `None`.
- `move_count`: total plies played.
- `castling_rights`: `K`, `Q`, `k`, `q` flags.
- `en_passant_square`: target square for en passant when available.
- `check_count`: per-side check counters for Three-Check.

The coordinate system is internal and consistent across the engine: row `0` is rank 1, row `7` is rank 8, column `0` is file `a`, and column `7` is file `h`.

### Move model

`core/move.py` defines a frozen `Move` dataclass:

```python
Move(start=(row, col), end=(row, col), promotion=None)
```

Moves can be serialized to UCI through `to_uci()`, including promotion moves such as `a7a8q`.

### Move generation and legality

`core/move_generation.py` contains the standard chess move generator. It includes:

- pawn pushes, double pushes, captures, promotion, and en passant;
- knight, bishop, rook, queen, and king move generation;
- castling generation with checks for occupied path squares, current check, through-check, and destination check;
- attack detection through `_is_square_attacked_raw()`;
- `generate_moves()` for pseudo-legal moves;
- `generate_legal_moves()` for check-filtered legal moves.

`core/apply_move.py` applies standard moves immutably by copying the board first. It handles normal movement, captures, castling rook movement, en passant capture removal, promotion, castling-right updates, en passant-square updates, side-to-move toggling, and move-count incrementing. Checkmate and stalemate are handled by the game loop, not by `apply_move()`.

## Supported variants

Variant behavior is routed through `variants/base.py`, which maps each variant name to its own move-application function and legal-move generator.

| Variant key | Implementation | Actual behavior in this repo |
|---|---|---|
| `standard` | `variants/standard.py` | Standard chess move application and legal move generation. |
| `atomic` | `variants/atomic.py` | Captures trigger explosions. Capturing piece, captured piece, and adjacent non-pawn pieces are removed. If a king is destroyed, the other side wins. Captures that explode the moving side's own king are filtered out. |
| `antichess` | `variants/antichess.py` | Captures are forced when available. Check is ignored. A side wins by losing all its pieces. |
| `kingofthehill` | `variants/king_of_the_hill.py` | Standard rules plus immediate win when a king reaches d4, e4, d5, or e5. |
| `threecheck` | `variants/three_check.py` | Standard rules plus immediate win when a side gives its third check. Check counts are stored on the board. |
| `chess960` | `variants/chess960.py` | Deterministic seeded Fischer-random starting position. Bishops are placed on opposite colors and the king is placed between rooks. Castling is intentionally disabled in this implementation. |
| `horde` | `variants/horde.py` | White starts with 36 pawns and no king. Black starts normally. Black wins by removing all White pieces. White uses pseudo-legal move generation because it has no king. |

There is also infrastructure for custom generated variants in `variants/llm_generate.py` and `variants/dynamic_loader.py`. That path expects generated Python functions matching the project interfaces. The default generator calls the OpenAI API through `OPENAI_API_KEY`; without that environment variable, generation returns an error instead of silently pretending to work.

## Evaluation features

All features are registered in `features/registry.py`. The current registry contains 12 feature functions:

| Feature | Purpose |
|---|---|
| `material` | Own material minus opponent material using standard piece values. |
| `negative_material` | Opponent material minus own material; useful for antichess-style objectives. |
| `piece_position` | Piece-square-table positional score. |
| `center_control` | Rewards occupying or attacking d4, e4, d5, and e5. |
| `king_safety` | Scores adjacent pawns, open-file exposure, and nearby enemy pieces. |
| `enemy_king_danger` | Scores proximity and pressure around the opponent king. |
| `king_proximity` | Counts own non-pawns adjacent to the enemy king minus opponent non-pawns adjacent to own king. |
| `mobility` | Own pseudo-legal move count minus opponent pseudo-legal move count. |
| `pawn_structure` | Penalizes doubled and isolated pawns; rewards passed and connected pawns. |
| `bishop_pair` | Adds a bishop-pair bonus relative to the opponent. |
| `rook_activity` | Rewards open files, semi-open files, and rook activity on the seventh rank. |
| `capture_threats` | Sums the material value of currently capturable enemy pieces. |

`agents/evaluation.py` evaluates a board by normalizing each raw feature value into `[-1, 1]`, multiplying by the agent's feature weight, and summing the result. Terminal boards return fixed win/loss/draw scores.

## Agent generation

`agents/generate_agents.py` creates feature-subset agents from the feature registry.

- If the full nonempty power set fits inside `max_agents`, it generates every nonempty subset.
- Otherwise, it uses stratified sampling: all single-feature agents, all pair-feature agents, the full-feature agent, then random larger subsets until `max_agents` is reached.
- Every generated agent uses equal weights across its selected features.
- Agent names are deterministic and follow `Agent_feature_a__feature_b`.

The agent object itself is defined in `agents/feature_subset_agent.py` and stores `name`, `features`, and `weights`.

## Search engine

`search/alpha_beta.py` implements a variant-aware depth-limited negamax search with alpha-beta pruning.

Important details:

- The engine obtains move generation and move application from `variants/base.py`, so search follows the selected variant's rules.
- Captures are ordered before quiet moves, sorted by captured-piece value.
- The engine tracks `nodes_searched` and `search_time_seconds` for each selected move.
- Evaluation is delegated to the selected feature-subset agent.

This is a simple research/search engine, not a production chess engine. It does not implement transposition tables, iterative deepening, quiescence search, opening books, time management, or NN evaluation.

## Game simulation and tournament pipeline

`simulation/game.py` owns the game loop. It creates the starting board for the selected variant, alternates between White and Black, requests legal moves, asks either `AlphaBetaEngine` or `RandomAgent` to select a move, applies the variant-specific move, and returns a `GameResult` dataclass.

A `GameResult` records:

- White and Black agent names;
- winner or draw;
- number of plies;
- termination reason;
- average searched nodes and time for each side;
- UCI move list.

`tournament/round_robin.py` runs every ordered pair of agents once, so `N` agents produce `N * (N - 1)` games. It supports serial execution by default and process-pool parallel execution through the `workers` argument.

`tournament/leaderboard.py` scores agents with:

```text
win = 1.0, draw = 0.5, loss = 0.0
score_rate = (wins + 0.5 * draws) / games_played
```

`analysis/feature_marginals.py` computes how much better agents with a feature perform compared with agents without it. `analysis/synergy.py` computes pairwise feature interaction using an ANOVA-style two-way interaction term:

```text
synergy(a, b) = avg_with_both - avg_with_a - avg_with_b + overall_avg
```

`reports/markdown_report.py` converts leaderboard, marginal, and synergy results into a Markdown strategy report.

`export_data.py` converts tournament JSON into CSV/JSON artifacts for dashboards and external inspection, including games, leaderboard, agents, feature marginals, synergies, matchup matrices, head-to-head summaries, termination breakdowns, game-length distributions, feature-count performance, feature-presence impact, and summary metadata.

## Interfaces

### CLI

The CLI is defined in `main.py` with Typer. Available commands are:

```bash
python main.py random-game
python main.py match
python main.py tournament
python main.py analyze
python main.py full-pipeline
python main.py play
```

Examples:

```bash
python main.py random-game --variant standard --max-moves 80 --seed 42
```

```bash
python main.py match \
  --white material,mobility \
  --black king_safety,center_control \
  --variant atomic \
  --depth 2 \
  --max-moves 80
```

```bash
python main.py tournament \
  --variant atomic \
  --depth 2 \
  --max-moves 80 \
  --max-agents 30 \
  --output outputs/data/tournament_results_atomic.json
```

```bash
python main.py full-pipeline \
  --variant standard \
  --depth 2 \
  --max-moves 80 \
  --max-agents 30 \
  --top-k 10
```

```bash
python main.py play --variant atomic --depth 3 --color w
```

### Streamlit UI

The main Streamlit app is `ui/app.py`. It provides:

- a home/overview page;
- variant selection;
- feature selection;
- live tournament execution;
- leaderboard, marginal, synergy, matchup, and chart panels;
- sample-game visualization;
- play-against-engine mode;
- optional custom-variant generation and dynamic loading flow.

The board UI is split across:

- `ui/board.py`: FEN-to-SVG board rendering helpers using `python-chess`;
- `ui/chess_viewer.py`: replay and drag-and-drop board components;
- `ui/play_engine.py`: UI-facing move legality, move application, engine reply, and game-status helpers;
- `ui/components/chess_dnd/index.html`: embedded browser chess board with drag/drop, legal-move highlighting, promotion UI, and explosion-square highlighting.

Run the UI with:

```bash
streamlit run ui/app.py
```

### FastAPI server

`api/server.py` exposes:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Health check. |
| `/api/features` | GET | Registered feature metadata. |
| `/api/variants` | GET | Supported variant names. |
| `/api/tournament` | POST | Runs a tournament and streams progress/completion through Server-Sent Events. |

Run the API with:

```bash
uvicorn api.server:app --reload --port 8000
```

## Installation

Use Python 3.11+ or a recent Python 3 version with support for modern type syntax.

```bash
python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The project uses local Python modules directly from the repository root. Run commands from the root directory so imports such as `from core.board import Board` resolve correctly.

## Common workflows

### Run a complete experiment

```bash
python main.py full-pipeline \
  --variant atomic \
  --depth 2 \
  --max-moves 80 \
  --seed 42 \
  --max-agents 30 \
  --top-k 10
```

This will:

1. load registered features;
2. generate feature-subset agents;
3. run a round-robin tournament;
4. compute the leaderboard;
5. compute feature marginals;
6. compute pairwise synergies;
7. save tournament JSON under `outputs/data/`;
8. write a Markdown report under `outputs/reports/`.

### Export visualization data

After a tournament JSON exists, use `export_data.py` to create CSV/JSON analysis artifacts.

```bash
python export_data.py \
  --input outputs/data/tournament_results_atomic.json \
  --output-dir outputs/data/atomic_viz \
  --variant atomic
```

### Run tests

```bash
pytest -q
```

The test suite covers the board model, standard move generation, move application, variants, feature functions, alpha-beta search, tournament logic, analysis logic, and UI play helpers.

## Verification status from this inspection

The repository source was inspected directly from the uploaded zip. A syntax-level compile check was run with:

```bash
python3 -m compileall -q agents analysis api core features reports search simulation tournament variants main.py export_data.py scripts ui
```

That compile check completed successfully.

Full test execution was not completed in this container because the system Python available for execution did not have `pytest` installed. The project declares `pytest>=8.0.0` in `requirements.txt`, so a normal project virtual environment should install it through `pip install -r requirements.txt` before running `pytest -q`.

## Current limitations

These are real limitations in the current codebase, not theoretical caveats:

- The alpha-beta engine is intentionally simple: no transposition table, no quiescence search, no iterative deepening, no opening book, and no clock-based time management.
- Feature-subset agents use equal weights only. The project compares feature inclusion/exclusion, but it does not optimize feature weights.
- Tournament strength is relative to other generated agents inside the same experiment. It is not an Elo estimate.
- Chess960 castling is disabled, even though Chess960 starting positions are generated.
- Antichess ignores check and treats kings as capturable pieces, consistent with the implementation's simplified antichess model.
- Horde uses pseudo-legal move generation for White because White has no king in this implementation.
- Pairwise synergy analysis only measures two-feature interactions; it does not model higher-order feature interactions.
- Custom variant generation depends on an external OpenAI API key unless the code path is replaced with a local model adapter.

## Output artifacts already present

The uploaded repository includes precomputed outputs under `outputs/`, including tournament JSON files for several variants and visualization-ready CSV/JSON directories for at least `standard` and `atomic`. These files are useful for demoing the UI or inspecting past runs, but they should not be treated as universal benchmarks unless the exact run configuration is documented alongside them.

## Engineering intent

EngineLab is best understood as a chess-variant evaluation laboratory. Its value is not in beating strong chess engines. Its value is in making variant strategy measurable: define features, generate controlled agents, run reproducible self-play, and convert the results into interpretable evidence about which heuristics matter under each rule set.
