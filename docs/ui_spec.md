# EngineLab UI Spec v2 — Lichess-Style

## Concept

Single-page app. Lichess layout: large chess board permanently on the left,
control/analysis panel on the right. User selects features to include in their
engine, builds it (runs the tournament), sees what won and why, then plays
against the best engine directly on the board.

---

## Layout

```
┌────────────────────────────────────────────────────────────────────┐
│  ♟ EngineLab                                                       │  ← top bar
├──────────────────────────────┬─────────────────────────────────────┤
│                              │                                     │
│                              │         RIGHT PANEL                 │
│        CHESS BOARD           │   (Build → Live → Analysis → Play) │
│     (always visible)         │                                     │
│                              │                                     │
│                              │                                     │
└──────────────────────────────┴─────────────────────────────────────┘
```

- **Left column (58%):** Chess board. Always shown. Reflects current mode.
- **Right column (42%):** Panel. Changes based on `st.session_state["view"]`.

---

## Views (right panel states)

### View 1 — Build  (`view = "build"`)
Default view. Let the user compose their engine.

**Elements:**
- Variant buttons: `Standard` | `Atomic` | `Antichess` (pill-style, one active)
- Feature section header: "Select Features"
- 10 feature checkboxes in a 2-column grid (default: all checked)
- Quick presets row: `Quick` (3 features) · `Standard` (5) · `Full` (10)
- Depth row: radio — `Fast (depth 1)` · `Normal (depth 2)` · `Deep (depth 3)`
- Estimated agents + games (live caption, no slider)
- `Build Engine` primary button (disabled if < 2 features selected)
- `Load Demo` secondary button (loads mock data, skips to Analysis)

**Board (left):** Starting position, static. No interaction.

---

### View 2 — Live  (`view = "live"`)
Shown while tournament is running.

**Elements:**
- Section: "Building…" with spinning indicator
- Progress bar
- `Games X / Y · Elapsed Ns · Est. Ns remaining`
- Live top-5 leaderboard table (agent name, score rate, W/D/L)
- `Cancel` button that sets running=False and returns to Build

**Board (left):** Starting position, static (live game data not available until engine is wired).

---

### View 3 — Analysis  (`view = "analysis"`)
Shown after tournament completes or demo data loaded.

**Elements (scrollable):**
- Success banner: "Tournament complete · N agents · N games · Xs"
- Best engine card: name, score rate, W/D/L record, features used (tag pills)
- `Play Against Best Engine ▶` prominent button → switches to Play view
- Horizontal divider
- **Feature Marginals** — compact horizontal bar chart (green/red, sorted)
- **Synergy Pairs** — top-5 positive + top-5 negative pairs (two small bar charts side by side)
- **Leaderboard** — dataframe, sortable, top 20 rows visible
- Download row: Markdown report button + JSON results button
- `Rebuild` text link → returns to Build view

**Board (left):** Replays the sample game. Arrow controls embedded below board.

---

### View 4 — Play  (`view = "play"`)
User plays against the best engine on the board.

**Elements (right panel):**
- Header: `You (White) vs [Best Engine Name] (Black)`
- Move list (PGN-style, scrollable, live-updating)
- Status line: whose turn, check/checkmate, draw
- `New Game` button · `Flip Board` toggle · `Resign` button
- Feature contribution panel: shows which features the engine weighted most
  on its last move (mock bar chart for now; live when engine is wired)
- `← Back to Analysis` link

**Board (left):**
- Interactive. User clicks a piece → valid destination squares highlight.
- After user move: engine responds (currently mock / random; real engine when Area 1 done).
- Last move highlighted. Check square highlighted red.
- Implemented via `st.components.v1.html()` chess component with JS→Python
  move communication via URL query params or Streamlit component bidirectional API.

---

## Board Component

File: `ui/chess_viewer.py`

Two rendering modes:

| Mode | Function | Description |
|------|----------|-------------|
| Static replay | `chess_game_viewer(moves, ...)` | Replays stored game, nav controls |
| Interactive play | `chess_play_board(fen, on_move_key, ...)` | User drags pieces, posts move back |

Colors: Lichess brown (`#b58863` / `#f0d9b5`). Pieces: chessboard.js Wikipedia set.
Board size: fills left column width (responsive, `width: 100%`).

For interactive play, the component emits the user's move as a UCI string via a
hidden Streamlit text input that the JS writes to via `window.parent.postMessage`
or the Streamlit component `setValue` bridge. On each Streamlit rerun, the engine
reads the new move, plays its reply, and re-renders the board.

---

## Colors — Lichess Dark Theme

| Token | Value | Use |
|-------|-------|-----|
| `bg-page` | `#161512` | Page background |
| `bg-panel` | `#1f1e1c` | Right panel background |
| `bg-card` | `#272522` | Cards / sections |
| `border` | `#3a3a38` | Subtle borders |
| `text-primary` | `#bababa` | Main text |
| `text-muted` | `#888` | Secondary text |
| `accent-green` | `#629924` | Active state, primary button |
| `accent-green-hover` | `#4e7a1b` | Button hover |
| `board-dark` | `#b58863` | Dark squares |
| `board-light` | `#f0d9b5` | Light squares |

---

## No Sliders

Sliders removed entirely. Replacements:
- **Depth** → `st.radio` with labels "Fast (1)" / "Normal (2)" / "Deep (3)", horizontal
- **Max moves** → fixed constant `80`
- **Workers** → `min(4, os.cpu_count() or 1)` auto
- **Seed** → fixed `42`

---

## Session State Keys

```python
# Config
"variant"             # "standard" | "atomic" | "antichess"
"selected_features"   # list[str]
"depth"               # 1 | 2 | 3

# View routing
"view"                # "build" | "live" | "analysis" | "play"

# Runtime
"running"             # bool
"progress"            # float 0–1
"games_completed"     # int
"total_games"         # int
"start_time"          # float | None
"error"               # str | None

# Results
"results"             # list[GameResult] | None
"agents"              # list[FeatureSubsetAgent] | None
"leaderboard"         # list[LeaderboardRow] | None
"marginals"           # list[FeatureContributionRow] | None
"synergies"           # list[SynergyRow] | None
"interpretation"      # str | None
"report_md"           # str | None
"config_snapshot"     # dict | None
"duration_seconds"    # float | None

# Game viewer (replay)
"sample_game_moves"   # list[str] UCI | None
"sample_game_white"   # str
"sample_game_black"   # str
"sample_game_result"  # str

# Play mode
"play_fen"            # str — current board FEN
"play_moves"          # list[str] UCI — full game so far
"play_status"         # "ongoing" | "checkmate" | "stalemate" | "draw"
"play_flipped"        # bool
```

---

## File Map

| File | Role |
|------|------|
| `ui/app.py` | Entry point; two-column layout; routes right panel by `view` |
| `ui/chess_viewer.py` | Board HTML component (replay + play modes) |
| `ui/mock_data.py` | Mock tournament data for demo / testing |
| `ui/constants.py` | Features, display names, colors, session defaults |
| `.streamlit/config.toml` | Lichess dark theme base |

---

## Acceptance Criteria

| # | Test |
|---|------|
| U1 | App loads at `streamlit run ui/app.py` with board visible and Build panel shown |
| U2 | Variant buttons change active highlight immediately |
| U3 | Feature checkboxes update agent/game count caption live |
| U4 | Quick presets correctly set feature selection |
| U5 | "Build Engine" disabled with < 2 features |
| U6 | "Load Demo" populates Analysis view with mock data |
| U7 | Analysis view shows marginals chart and leaderboard |
| U8 | "Play Against Best Engine" transitions board to interactive play |
| U9 | Board shows starting position and accepts clicks in Play mode |
| U10 | Move list updates after each move in Play mode |
| U11 | "New Game" resets the board in Play mode |
| U12 | Running a real tournament (standard, depth 1, 3 features) completes and shows Analysis |
| U13 | Download buttons produce valid files |

---

## Out of Scope

- Real engine response in Play mode (mock random move until Area 1 ships)
- Atomic / Antichess interactive play (variant stubs raise NotImplementedError)
- Cross-variant comparison tab
- User accounts / saved results
- Mobile layout
