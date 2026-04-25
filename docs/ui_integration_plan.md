# UI Integration & Deployment Plan

## Context

The EngineLab backend is fully implemented -- chess engine, 3 variants
(standard, atomic, antichess), 10 evaluation features, agent generation,
alpha-beta search, round-robin tournament, analysis (marginals + synergy),
and Markdown report generation all work end-to-end via the CLI (`main.py`).

Pre-computed tournament results exist in `outputs/data/` for both standard
and atomic chess. The frontend (`ui/app.py`) is a 7-line stub that raises
`NotImplementedError`. A detailed UI spec exists at `docs/ui_spec.md`
(912 lines).

This document describes everything required to connect the working backend
to a Streamlit frontend and deploy it.

---

## 1. Current State

### Backend (fully implemented)

| Component | Key Files | Status |
|-----------|-----------|--------|
| Chess engine | `core/board.py`, `core/move_generation.py`, `core/apply_move.py` | Complete |
| Standard chess | `variants/standard.py` | Complete |
| Atomic chess | `variants/atomic.py` | Complete |
| Antichess | `variants/antichess.py` | Complete |
| 10 features | `features/material.py`, `features/mobility.py`, etc. | Complete |
| Agent generation | `agents/generate_agents.py` | Complete |
| Evaluation | `agents/evaluation.py` | Complete |
| Alpha-beta search | `search/alpha_beta.py` | Complete |
| Game simulation | `simulation/game.py` | Complete |
| Round-robin tournament | `tournament/round_robin.py` | Complete |
| Leaderboard | `tournament/leaderboard.py` | Complete |
| Results I/O | `tournament/results_io.py` | Complete |
| Feature marginals | `analysis/feature_marginals.py` | Complete |
| Pairwise synergy | `analysis/synergy.py` | Complete |
| Interpretation | `analysis/interpretation.py` | Complete |
| Report generation | `reports/markdown_report.py` | Complete |
| CLI | `main.py` (typer) | Complete |

### Frontend (not implemented)

| Component | Status |
|-----------|--------|
| `ui/app.py` | 7-line stub, raises `NotImplementedError` |
| `ui/pages/` directory | Does not exist |
| `ui/board.py` helper | Does not exist |
| `.streamlit/config.toml` | Does not exist |
| Deployment config | None (no Dockerfile, Procfile, or vercel.json) |

### Pre-computed Data

```
outputs/data/tournament_results_standard.json   (28 KB, 90 games)
outputs/data/tournament_results_atomic.json     (29 KB, 90 games)
outputs/reports/standard_strategy_report.md
outputs/reports/atomic_strategy_report.md
```

---

## 2. Backend Gaps

Five things the UI needs that the backend does not currently provide.

### Gap A: `Board.to_fen()` method

**File:** `core/board.py`

The UI spec requires board rendering via `chess.svg.board()` from the
`python-chess` library, which accepts FEN strings. The custom `Board`
class has no FEN export.

**Solution:** Add a `to_fen(self) -> str` method that converts `grid`,
`side_to_move`, `castling_rights`, `en_passant_square`, and `move_count`
into a standard FEN string. ~20 lines.

```python
def to_fen(self) -> str:
    """Convert board state to FEN string."""
    rows = []
    for rank in range(7, -1, -1):
        empty = 0
        row_str = ""
        for col in range(8):
            piece = self.grid[rank][col]
            if piece is None:
                empty += 1
            else:
                if empty > 0:
                    row_str += str(empty)
                    empty = 0
                row_str += piece
        if empty > 0:
            row_str += str(empty)
        rows.append(row_str)

    castling = ""
    for c in ["K", "Q", "k", "q"]:
        if self.castling_rights.get(c, False):
            castling += c
    if not castling:
        castling = "-"

    ep = "-"
    if self.en_passant_square is not None:
        from core.coordinates import square_to_algebraic
        ep = square_to_algebraic(*self.en_passant_square)

    return f"{'/'.join(rows)} {self.side_to_move} {castling} {ep} 0 {self.move_count // 2 + 1}"
```

### Gap B: Move history in `GameResult`

**File:** `simulation/game.py`

`GameResult` only stores summary stats (`moves: int`, `winner`,
`termination_reason`). Game replay (Page 5) and the live game viewer
(Page 2) need the actual move sequence.

**Solution:** Add `move_list: list[str]` field to `GameResult`. In
`play_game()`, append `move.to_uci()` after each move. Update
`tournament/results_io.py` to serialize/deserialize the new field.

```python
@dataclass
class GameResult:
    # ... existing fields ...
    move_list: list[str] = field(default_factory=list)  # UCI strings
```

Impact: ~2 bytes per ply, ~600 KB extra across 7500 games at 40 plies
average. Existing JSON results in `outputs/data/` would need regeneration
to include move lists, or the replay feature must handle missing data
gracefully.

### Gap C: Progress callback in `run_round_robin()`

**File:** `tournament/round_robin.py`

Currently uses `tqdm` in a tight loop. The UI needs a callback to update
`st.session_state` with live progress.

**Solution:** Add optional parameter:

```python
def run_round_robin(
    agents, variant, depth, max_moves, seed,
    on_game_complete=None,  # Callable(games_done, total, result) | None
) -> list[GameResult]:
```

After each game, call `on_game_complete(len(results), total, result)` if
provided. Backward compatible -- existing CLI code passes nothing.

### Gap D: Missing Python dependencies

**File:** `requirements.txt`

Add:
```
plotly>=5.0.0       # interactive charts (Plotly is used throughout the UI spec)
chess>=1.10.0       # python-chess for SVG board rendering
```

### Gap E: Streamlit theme configuration

**File:** `.streamlit/config.toml` (create new)

```toml
[theme]
base = "dark"
primaryColor = "#00e676"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#161b22"
textColor = "#e6edf3"
font = "monospace"
```

---

## 3. UI Implementation

### 3.1 Architecture

```
ui/
├── app.py                   # Entry point: sidebar, session state, thread launcher
├── board.py                 # Shared helper: Board -> FEN -> chess.svg -> SVG string
└── pages/
    ├── 1_lab.py             # Home / configure / load previous results
    ├── 2_tournament.py      # Live progress + completed tournament view
    ├── 3_analysis.py        # Tabbed analysis (leaderboard, features, synergy)
    ├── 4_explorer.py        # Build-your-own-engine interactive tool
    └── 5_play_watch.py      # Game replay + human vs engine
```

Launch with: `streamlit run ui/app.py`

### 3.2 Integration Map

Each page calls existing backend functions. No new backend logic is needed
beyond the gaps above.

#### `ui/app.py` -- Sidebar + orchestration

```
Backend calls:
  features.registry.get_feature_names()          -> populate checkbox list
  features.registry.FEATURE_DESCRIPTIONS         -> checkbox help text
  agents.generate_agents.generate_feature_subset_agents()  -> agent count preview

Background thread (_run_tournament) calls the full pipeline:
  1. generate_feature_subset_agents(features, max_agents, seed)
  2. run_round_robin(agents, variant, depth, max_moves, seed, on_game_complete=callback)
  3. compute_leaderboard(results, agents)
  4. compute_feature_marginals(leaderboard, feature_names, top_k)
  5. compute_pairwise_synergies(leaderboard, feature_names)
  6. generate_interpretation(best_agent, marginals, synergies, variant)
  7. generate_markdown_report(...)

All results stored in st.session_state.
```

#### `ui/board.py` -- Board rendering helper

```python
import chess
import chess.svg
from core.board import Board

def render_board_svg(board: Board, last_move=None, size=400) -> str:
    fen = board.to_fen()
    chess_board = chess.Board(fen)
    # Optionally highlight last move, exploded squares, etc.
    return chess.svg.board(chess_board, size=size)
```

Used by Pages 2, 4, and 5.

#### `ui/pages/1_lab.py` -- Home page

```
Reads:  st.session_state config keys
Calls:  tournament.results_io.load_results_json()  (for loading saved results)
        pathlib.Path.glob("outputs/data/*.json")   (scan for existing files)
```

Content: pipeline diagram, preset buttons (Debug/Small/Medium/Full),
load previous results file picker.

#### `ui/pages/2_tournament.py` -- Tournament view

Two states:

**Live state** (tournament running):
```
Reads from session state (updated by background thread):
  progress, games_completed, total_games, start_time
Calls:
  tournament.leaderboard.compute_leaderboard()  (partial, on results-so-far)
  ui.board.render_board_svg()                   (live game mini-viewer)
```

**Completed state** (tournament done):
```
Reads:  st.session_state["leaderboard"], ["marginals"]
```

Displays: progress bar, emerging leaderboard, summary cards, top features.

#### `ui/pages/3_analysis.py` -- Analysis (5 tabs)

Pure visualization. All data from `st.session_state`, no direct backend calls.

| Tab | Data Source | Visualization |
|-----|-------------|---------------|
| Leaderboard | `session_state["leaderboard"]` | `st.dataframe` + Plotly bar chart |
| Feature Intelligence | `session_state["marginals"]` | Plotly horizontal bar chart |
| Synergy Matrix | `session_state["synergies"]` | Plotly heatmap (`go.Heatmap`) |
| Cross-Variant | `session_state["all_results"]` | Side-by-side comparison charts |
| Report | `session_state["report_md"]` | `st.markdown()` + download button |

Easiest page to build and test.

#### `ui/pages/4_explorer.py` -- Build-your-own-engine

```
Reads:  st.session_state["leaderboard"]   -> look up actual win rate
        st.session_state["marginals"]      -> sum marginal contributions
Displays: Plotly waterfall chart (go.Waterfall) for feature contributions
```

User picks features via checkboxes, sees predicted vs actual performance.

#### `ui/pages/5_play_watch.py` -- Replay + Play

**Mode A (Watch a game):**
```
Reads:  st.session_state["results"]       -> pick a game
Uses:   GameResult.move_list              -> step through moves (requires Gap B)
Calls:  ui.board.render_board_svg()       -> render each position
        agents.evaluation.contributions() -> per-move feature breakdown
```

**Mode B (Play vs engine):**
```
Calls:  agents.feature_subset_agent.FeatureSubsetAgent()  -> construct agent
        search.alpha_beta.AlphaBetaEngine.choose_move()   -> engine moves
        agents.evaluation.contributions()                  -> transparency panel
Uses:   chessboard.js via st.components.v1.html()          -> interactive board
```

Most complex page. Depends on Gaps A and B being resolved.

### 3.3 Threading Model

```
Main thread (Streamlit):
  - Renders UI
  - Reads from st.session_state
  - Polls for updates via st.fragment or periodic rerun

Background thread (tournament):
  - Runs the full pipeline
  - Writes to st.session_state behind a threading.Lock
  - Calls on_game_complete callback to update progress
  - Never calls st.rerun() directly (only sets a flag)
```

---

## 4. Deployment

### Option 1: Streamlit Cloud (recommended for demos)

**Pros:** Zero-config, free tier, HTTPS, auto-deploys from GitHub.

**Cons:** ~1 GB RAM limit, limited CPU. Full tournaments (10 features,
depth 2, ~6K games) will timeout. Depth 1 with 3 features (~42 games)
should work.

**Setup:**
1. Push repo to GitHub (already done)
2. Connect repo at share.streamlit.io
3. Set entry point to `ui/app.py`
4. `.streamlit/config.toml` and `requirements.txt` are auto-detected
5. Ship pre-computed `outputs/data/*.json` in the repo for "Load Results" mode

**Best strategy:** Deploy with pre-computed data as the default experience.
Limit the live "Run Tournament" to small configs (Debug/Small presets only).

### Option 2: Docker (recommended for full capability)

**Setup:** Create `Dockerfile` at repo root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "ui/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
```

Can deploy to: Railway, Fly.io, Google Cloud Run, AWS ECS, DigitalOcean
App Platform, or any VPS.

**Pros:** Full CPU access, no timeout limits, predictable environment.

### Option 3: Vercel (not recommended)

Streamlit requires a persistent WebSocket connection. Vercel's serverless
model fundamentally conflicts with this:
- Serverless functions have execution time limits
- No persistent WebSocket support for Streamlit's bidirectional protocol
- Tournament computation can run for minutes

If Vercel deployment is mandatory, the frontend would need to be rewritten
in Next.js/React with API routes calling the Python backend as a
microservice. This is a much larger project.

---

## 5. Build Sequence

Ordered by dependency and priority. Earlier phases unblock later ones.

| Phase | Work | Files | Depends On | Est. Hours |
|-------|------|-------|------------|-----------|
| 0a | Add `plotly`, `chess` to requirements | `requirements.txt` | -- | 0.1 |
| 0b | Create Streamlit theme config | `.streamlit/config.toml` | -- | 0.1 |
| 0c | Add `Board.to_fen()` | `core/board.py` | -- | 0.5 |
| 0d | Add `move_list` to `GameResult` | `simulation/game.py`, `tournament/results_io.py` | -- | 1.0 |
| 0e | Add progress callback to round-robin | `tournament/round_robin.py` | -- | 0.5 |
| 1 | Entry point + sidebar + threading | `ui/app.py` | 0a-0e | 3.0 |
| 2 | Board rendering helper | `ui/board.py` | 0c | 1.0 |
| 3 | Analysis page (5 tabs) | `ui/pages/3_analysis.py` | 1 | 4.0 |
| 4 | Game replay (Mode A) | `ui/pages/5_play_watch.py` | 1, 2, 0d | 3.0 |
| 5 | Tournament completed state | `ui/pages/2_tournament.py` | 1 | 2.0 |
| 6 | Tournament live state | `ui/pages/2_tournament.py` | 1, 0e | 4.0 |
| 7 | Home page + presets + load | `ui/pages/1_lab.py` | 1 | 2.0 |
| 8 | Explorer (waterfall + what-if) | `ui/pages/4_explorer.py` | 1, 3 | 3.0 |
| 9 | Interactive play (Mode B) | `ui/pages/5_play_watch.py` | 2, 0c | 4.0 |
| 10 | Cross-variant comparison tab | `ui/pages/3_analysis.py` | 3 | 1.5 |
| 11 | Dockerfile + deployment config | `Dockerfile` | All | 1.0 |
| 12 | Integration testing + polish | -- | All | 3.0 |
| **Total** | | | | **~33** |

### Minimum Viable Demo

To get a working demo that loads pre-computed results and shows analysis
charts (no live tournament, no interactive play):

Phases 0a, 0b, 0c, 1, 2, 3, 5, 7 = **~14 hours**

---

## 6. Risk Areas

1. **Live tournament viewer (Page 2, live state)** -- Coordinating a
   CPU-intensive background thread with Streamlit's rerun model is the
   hardest integration challenge. Budget extra time.

2. **Interactive play (Page 5, Mode B)** -- The chessboard.js embed via
   `st.components.v1.html()` requires a JavaScript-to-Python bridge
   (postMessage to hidden text_input) that is fragile and has latency.

3. **Streamlit Cloud CPU limits** -- Full tournaments will likely timeout.
   Plan for "Results mode" as the primary deployed experience.

4. **Existing JSON results lack move lists** -- After Gap B is resolved,
   existing `outputs/data/*.json` files must be regenerated to include
   move history, or the replay feature must handle missing data.

---

## 7. Verification Checklist

- [ ] `pip install -r requirements.txt` succeeds with plotly + chess
- [ ] `streamlit run ui/app.py` launches without error
- [ ] Sidebar renders: variant radio, feature checkboxes, depth slider
- [ ] Load `outputs/data/tournament_results_standard.json` -> leaderboard renders
- [ ] Analysis page: all 5 tabs display charts/tables
- [ ] Run debug tournament (2 features, depth 1, max 20 moves) -> completes in-browser
- [ ] Live tournament page shows progress bar and emerging leaderboard
- [ ] Game replay steps through moves with board visualization
- [ ] `docker build -t enginelab . && docker run -p 8501:8501 enginelab` serves the app
- [ ] `pytest` still passes after all changes
