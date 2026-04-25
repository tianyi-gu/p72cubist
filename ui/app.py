from __future__ import annotations

import os
import sys
import threading
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.constants import ALL_FEATURES, FEATURE_DISPLAY_NAMES
from ui.board import render_board, starting_fen
from ui.chess_viewer import chess_game_viewer

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EngineLab",
    page_icon="♟",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS — Lichess dark theme
# ---------------------------------------------------------------------------

_CSS = """
<style>
body, .stApp { background: #161512 !important; }

.block-container {
    padding-top: 0.5rem !important;
    max-width: 100% !important;
}

h3 {
    color: #bababa !important;
    border-left: 3px solid #629924;
    padding-left: 8px;
}

/* Primary button: Lichess green */
div[data-testid="stButton"] > button[kind="primary"] {
    background: #629924 !important;
    color: #0e1117 !important;
    font-weight: 700 !important;
    border: none !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #4e7a1b !important;
}

/* Dataframes */
div[data-testid="stDataFrame"] {
    border: 1px solid #3a3a38;
    border-radius: 6px;
    overflow: hidden;
}

/* Metric cards */
div[data-testid="metric-container"] {
    background: #272522;
    border: 1px solid #3a3a38;
    border-radius: 8px;
    padding: 12px 16px !important;
}

/* Alerts */
div[data-testid="stAlert"] { border-radius: 8px !important; }

/* General text */
p, label, .stMarkdown { color: #bababa !important; }

hr { border-color: #3a3a38 !important; }

/* Scrollable move list */
.move-list-scroll {
    background: #272522;
    border: 1px solid #3a3a38;
    border-radius: 6px;
    padding: 8px 12px;
    max-height: 280px;
    overflow-y: auto;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    color: #bababa;
    line-height: 1.8;
}
</style>
"""

# ---------------------------------------------------------------------------
# Header HTML
# ---------------------------------------------------------------------------

HEADER_HTML = """
<div style="background:#272522;border-left:4px solid #629924;
            padding:10px 20px;margin-bottom:12px;display:flex;
            align-items:center;gap:10px;">
    <span style="font-size:1.5rem;">♟</span>
    <span style="font-size:1.2rem;font-weight:700;color:#bababa;
                 letter-spacing:-0.3px;">EngineLab</span>
    <span style="font-size:0.8rem;color:#888;margin-left:6px;">
        Feature-subset strategy discovery for chess variants
    </span>
</div>
"""

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

SESSION_DEFAULTS: dict = {
    "variant": "standard",
    "selected_features": list(ALL_FEATURES),
    "depth": 2,
    "view": "build",
    "running": False,
    "progress": 0.0,
    "games_completed": 0,
    "total_games": 0,
    "start_time": None,
    "error": None,
    "results": None,
    "agents": None,
    "leaderboard": None,
    "marginals": None,
    "synergies": None,
    "interpretation": None,
    "report_md": None,
    "config_snapshot": None,
    "duration_seconds": None,
    "sample_game_moves": None,
    "sample_game_white": "White",
    "sample_game_black": "Black",
    "sample_game_result": "",
    "play_fen": chess.STARTING_FEN,
    "play_moves": [],
    "play_status": "ongoing",
    "play_flipped": False,
}

VARIANT_DESCRIPTIONS = {
    "standard": "Win by checkmating the king.",
    "atomic": "Captures cause explosions.",
    "antichess": "Lose all your pieces to win.",
}

PRESETS = {
    "Quick":    ["material", "king_safety", "capture_threats"],
    "Standard": ["material", "king_safety", "capture_threats", "mobility", "enemy_king_danger"],
    "Full":     list(ALL_FEATURES),
}

_CHART_THEME = dict(
    paper_bgcolor="#272522",
    plot_bgcolor="#1f1e1c",
    font=dict(color="#bababa"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_session_state() -> None:
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = list(default) if isinstance(default, list) else default


def _agent_short_name(name: str) -> str:
    return name.replace("Agent_", "").replace("__", " + ")


def _feature_pills(features: tuple | list) -> str:
    """Return HTML pill spans for a list of feature keys."""
    pills = []
    for f in features:
        label = FEATURE_DISPLAY_NAMES.get(f, f)
        pills.append(
            f'<span style="background:#1f1e1c;border:1px solid #629924;'
            f'color:#bababa;border-radius:4px;padding:2px 7px;'
            f'font-size:11px;margin:2px;">{label}</span>'
        )
    return " ".join(pills)


def _est_agents_games(features: list[str]) -> tuple[int, int]:
    n = len(features)
    n_agents = min(2 ** n - 1, 100) if n >= 1 else 0
    n_games = n_agents * (n_agents - 1)
    return n_agents, n_games


# ---------------------------------------------------------------------------
# Tournament thread
# ---------------------------------------------------------------------------

def _run_tournament(config: dict) -> None:
    try:
        import pathlib
        from agents.generate_agents import generate_feature_subset_agents
        from analysis.feature_marginals import compute_feature_marginals
        from analysis.interpretation import generate_interpretation
        from analysis.synergy import compute_pairwise_synergies
        from reports.markdown_report import generate_markdown_report
        from tournament.leaderboard import compute_leaderboard
        from tournament.round_robin import run_round_robin

        st.session_state["start_time"] = time.time()

        agents = generate_feature_subset_agents(
            config["selected_features"], max_agents=100, seed=config["seed"]
        )
        st.session_state["agents"] = agents
        total = len(agents) * (len(agents) - 1)
        st.session_state["total_games"] = total

        def _on_game(done: int, total: int) -> None:
            st.session_state["games_completed"] = done
            st.session_state["progress"] = done / total if total else 0.0

        results = run_round_robin(
            agents=agents,
            variant=config["variant"],
            depth=config["depth"],
            max_moves=config["max_moves"],
            seed=config["seed"],
            workers=config["workers"],
            on_game_complete=_on_game,
        )
        st.session_state["results"] = results

        leaderboard = compute_leaderboard(results, agents)
        marginals = compute_feature_marginals(leaderboard, config["selected_features"])
        synergies = compute_pairwise_synergies(leaderboard, config["selected_features"])
        interpretation = generate_interpretation(
            leaderboard[0] if leaderboard else None, marginals, synergies, config["variant"]
        )

        out = pathlib.Path("outputs/reports")
        out.mkdir(parents=True, exist_ok=True)
        report_path = str(out / f"{config['variant']}_strategy_report.md")
        generate_markdown_report(
            variant=config["variant"],
            feature_names=config["selected_features"],
            leaderboard=leaderboard,
            marginals=marginals,
            synergies=synergies,
            interpretation=interpretation,
            output_path=report_path,
            config=config,
        )
        report_md = pathlib.Path(report_path).read_text()

        st.session_state.update(
            leaderboard=leaderboard,
            marginals=marginals,
            synergies=synergies,
            interpretation=interpretation,
            report_md=report_md,
            config_snapshot=config,
            duration_seconds=time.time() - st.session_state["start_time"],
            view="analysis",
        )
    except Exception as exc:
        import traceback
        st.session_state["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    finally:
        st.session_state["running"] = False


def _start_tournament() -> None:
    config = {
        "variant": st.session_state["variant"],
        "selected_features": list(st.session_state["selected_features"]),
        "depth": st.session_state["depth"],
        "max_moves": 80,
        "workers": min(4, os.cpu_count() or 1),
        "seed": 42,
    }
    for k in ["results", "agents", "leaderboard", "marginals", "synergies",
              "interpretation", "report_md", "config_snapshot", "duration_seconds", "error"]:
        st.session_state[k] = None
    st.session_state.update(running=True, games_completed=0, progress=0.0, view="live")
    threading.Thread(target=_run_tournament, args=(config,), daemon=True).start()
    st.rerun()


# ---------------------------------------------------------------------------
# Engine reply (mock)
# ---------------------------------------------------------------------------

def _engine_reply(fen: str) -> str | None:
    """Pick a random legal move from the given FEN (seeded). Returns UCI string."""
    board = chess.Board(fen)
    if board.is_game_over():
        return None
    legal = list(board.legal_moves)
    if not legal:
        return None
    rng = random.Random(42 + len(st.session_state.get("play_moves", [])))
    return rng.choice(legal).uci()


# ---------------------------------------------------------------------------
# Board area (left column)
# ---------------------------------------------------------------------------

def _render_board_area() -> None:
    view = st.session_state.get("view", "build")

    if view == "analysis":
        moves = st.session_state.get("sample_game_moves")
        if moves:
            white = _agent_short_name(st.session_state.get("sample_game_white", "White"))
            black = _agent_short_name(st.session_state.get("sample_game_black", "Black"))
            result = st.session_state.get("sample_game_result", "")
            chess_game_viewer(moves=moves, white_name=white, black_name=black,
                              result=result, board_size=380, height=560)
            return

    if view == "play":
        fen = st.session_state.get("play_fen", chess.STARTING_FEN)
        flipped = st.session_state.get("play_flipped", False)
        last_move = (st.session_state.get("play_moves") or [None])[-1]
        svg = render_board(fen, last_move_uci=last_move, size=480, flipped=flipped)
        st.image(svg, use_container_width=True)
        return

    # Build / Live: static starting position
    svg = render_board(starting_fen(), size=480)
    st.image(svg, use_container_width=True)


# ---------------------------------------------------------------------------
# Build panel
# ---------------------------------------------------------------------------

def _render_build_panel() -> None:
    st.markdown("### Build Engine")

    # Variant selector
    variants = ["standard", "atomic", "antichess"]
    v_cols = st.columns(3)
    for col, v in zip(v_cols, variants):
        active = st.session_state["variant"] == v
        border_color = "#629924" if active else "#3a3a38"
        col.markdown(
            f'<div style="border:2px solid {border_color};border-radius:8px;'
            f'padding:8px 12px;background:#272522;margin-bottom:4px;">'
            f'<div style="font-weight:600;color:#bababa;">{v.title()}</div>'
            f'<div style="font-size:11px;color:#888;">{VARIANT_DESCRIPTIONS[v]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if col.button(
            "✓ Selected" if active else "Select",
            key=f"variant_btn_{v}",
            use_container_width=True,
        ):
            st.session_state["variant"] = v
            st.rerun()

    st.divider()

    # Preset buttons
    st.markdown("**Select Features**")
    p_cols = st.columns(3)
    for col, (label, feats) in zip(p_cols, PRESETS.items()):
        if col.button(label, key=f"preset_{label}", use_container_width=True):
            st.session_state["selected_features"] = list(feats)
            st.rerun()

    # Feature checkboxes — 2-col grid
    selected: list[str] = []
    cb_cols = st.columns(2)
    for i, feat in enumerate(ALL_FEATURES):
        checked = feat in st.session_state["selected_features"]
        if cb_cols[i % 2].checkbox(
            FEATURE_DISPLAY_NAMES[feat],
            value=checked,
            key=f"feat_{feat}",
        ):
            selected.append(feat)
    st.session_state["selected_features"] = selected

    n_agents, n_games = _est_agents_games(selected)
    st.caption(f"Est. **{n_agents}** agents · **{n_games:,}** games")
    if n_games > 5000:
        st.warning("Over 5,000 games — this may take a while.")

    st.divider()

    # Depth radio
    depth_labels = ["Fast (1)", "Normal (2)", "Deep (3)"]
    depth_choice = st.radio(
        "Search Depth",
        depth_labels,
        index=st.session_state["depth"] - 1,
        horizontal=True,
        key="depth_radio",
    )
    st.session_state["depth"] = depth_labels.index(depth_choice) + 1

    st.divider()

    can_run = len(selected) >= 2
    if not can_run:
        st.caption("Select at least 2 features to build.")

    build_col, demo_col = st.columns([3, 2])
    if build_col.button(
        "Build Engine",
        type="primary",
        use_container_width=True,
        disabled=not can_run,
    ):
        _start_tournament()

    if demo_col.button("Load Demo", use_container_width=True):
        from ui.mock_data import generate_mock_session_state
        state = generate_mock_session_state()
        state["view"] = "analysis"
        st.session_state.update(state)
        st.rerun()


# ---------------------------------------------------------------------------
# Live panel
# ---------------------------------------------------------------------------

def _render_live_panel() -> None:
    snap = st.session_state.get("config_snapshot") or {}
    variant = snap.get("variant", st.session_state.get("variant", "standard"))
    n_agents = len(st.session_state.get("agents") or [])
    total = st.session_state.get("total_games", 0)
    done = st.session_state.get("games_completed", 0)
    progress = st.session_state.get("progress", 0.0)
    start = st.session_state.get("start_time") or time.time()
    elapsed = time.time() - start
    remaining = (elapsed / progress - elapsed) if progress > 0.01 else 0.0

    with st.spinner("Building…"):
        st.markdown("### Building…")
        st.progress(progress)
        st.caption(
            f"Games **{done}** / **{total}**  ·  "
            f"Elapsed: **{elapsed:.0f}s**  ·  "
            f"Est. remaining: **{remaining:.0f}s**"
        )
        st.caption(f"Variant: **{variant.title()}** · **{n_agents}** agents")

        st.divider()

        lb = st.session_state.get("leaderboard")
        if lb:
            st.markdown("**Top 5 so far**")
            top5 = [
                {
                    "Agent": _agent_short_name(r.agent_name)[:40],
                    "Score Rate": round(r.score_rate, 4),
                    "W": r.wins,
                    "D": r.draws,
                    "L": r.losses,
                }
                for r in lb[:5]
            ]
            st.dataframe(
                pd.DataFrame(top5),
                use_container_width=True,
                hide_index=True,
                column_config={"Score Rate": st.column_config.NumberColumn(format="%.4f")},
            )
        else:
            st.info("Waiting for first results…")

        if st.button("Cancel", use_container_width=True):
            st.session_state["running"] = False
            st.session_state["view"] = "build"
            st.rerun()

    time.sleep(2)
    st.rerun()


# ---------------------------------------------------------------------------
# Analysis panel
# ---------------------------------------------------------------------------

def _render_analysis_panel() -> None:
    lb = st.session_state.get("leaderboard") or []
    marginals = st.session_state.get("marginals") or []
    synergies = st.session_state.get("synergies") or []
    snap = st.session_state.get("config_snapshot") or {}
    duration = st.session_state.get("duration_seconds")
    n_agents = len(st.session_state.get("agents") or lb)
    n_games = len(st.session_state.get("results") or [])
    variant = snap.get("variant", st.session_state.get("variant", "standard"))

    # Success banner
    dur_str = f"{duration:.0f}s" if duration else "—"
    st.success(
        f"Tournament complete · **{variant.title()}** · "
        f"**{n_agents}** agents · **{n_games}** games · **{dur_str}**"
    )

    # Best engine card
    if lb:
        best = lb[0]
        short = _agent_short_name(best.agent_name)
        st.markdown(
            f'<div style="background:#272522;border:1px solid #3a3a38;'
            f'border-radius:8px;padding:14px 16px;margin-bottom:10px;">'
            f'<div style="font-size:1rem;font-weight:700;color:#bababa;">{short}</div>'
            f'<div style="color:#629924;font-size:0.85rem;margin:4px 0;">'
            f'Score rate: {best.score_rate:.4f} &nbsp;·&nbsp; '
            f'W {best.wins} / D {best.draws} / L {best.losses}</div>'
            f'<div style="margin-top:6px;">{_feature_pills(best.features)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if st.button("Play Against Best Engine ▶", type="primary", use_container_width=True):
            st.session_state["view"] = "play"
            st.session_state["play_fen"] = chess.STARTING_FEN
            st.session_state["play_moves"] = []
            st.session_state["play_status"] = "ongoing"
            st.rerun()

    st.divider()

    # Feature marginals chart
    if marginals:
        st.markdown("### Feature Marginals")
        sorted_m = sorted(marginals, key=lambda r: r.marginal, reverse=True)
        labels = [FEATURE_DISPLAY_NAMES.get(r.feature, r.feature) for r in sorted_m]
        values = [r.marginal for r in sorted_m]
        colors = ["#629924" if v >= 0 else "#ff4d4d" for v in values]
        fig = go.Figure(go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=colors,
            hovertemplate="%{y}: %{x:+.4f}<extra></extra>",
        ))
        fig.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=4, b=0),
            yaxis=dict(autorange="reversed"),
            xaxis_title="Marginal contribution",
            **_CHART_THEME,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Synergy top/bottom side by side
    if synergies:
        st.markdown("### Synergy Pairs")
        sorted_s = sorted(synergies, key=lambda r: r.synergy, reverse=True)
        top5 = sorted_s[:5]
        bot5 = sorted_s[-5:][::-1]

        def _pair_label(r) -> str:
            a = FEATURE_DISPLAY_NAMES.get(r.feature_a, r.feature_a)
            b = FEATURE_DISPLAY_NAMES.get(r.feature_b, r.feature_b)
            return f"{a[:12]} + {b[:12]}"

        syn_left, syn_right = st.columns(2)
        with syn_left:
            st.caption("Top 5 positive pairs")
            fig_pos = go.Figure(go.Bar(
                x=[r.synergy for r in top5],
                y=[_pair_label(r) for r in top5],
                orientation="h",
                marker_color="#629924",
            ))
            fig_pos.update_layout(
                height=220, margin=dict(l=0, r=0, t=4, b=0),
                yaxis=dict(autorange="reversed"),
                **_CHART_THEME,
            )
            st.plotly_chart(fig_pos, use_container_width=True)

        with syn_right:
            st.caption("Top 5 negative pairs")
            fig_neg = go.Figure(go.Bar(
                x=[r.synergy for r in bot5],
                y=[_pair_label(r) for r in bot5],
                orientation="h",
                marker_color="#ff4d4d",
            ))
            fig_neg.update_layout(
                height=220, margin=dict(l=0, r=0, t=4, b=0),
                yaxis=dict(autorange="reversed"),
                **_CHART_THEME,
            )
            st.plotly_chart(fig_neg, use_container_width=True)

    st.divider()

    # Leaderboard dataframe (top 20)
    if lb:
        st.markdown("### Leaderboard")
        rows = [
            {
                "Rank": i + 1,
                "Agent": _agent_short_name(r.agent_name)[:50],
                "Features": len(r.features),
                "Score Rate": round(r.score_rate, 4),
                "W": r.wins,
                "D": r.draws,
                "L": r.losses,
                "Avg Length": round(r.avg_game_length, 1),
            }
            for i, r in enumerate(lb[:20])
        ]
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={"Score Rate": st.column_config.NumberColumn(format="%.4f")},
        )

    # Downloads
    report_md = st.session_state.get("report_md") or ""
    results = st.session_state.get("results") or []
    if report_md or results:
        st.markdown("**Downloads**")
        dl_left, dl_right = st.columns(2)
        if report_md:
            dl_left.download_button(
                "⬇ Markdown Report",
                data=report_md,
                file_name=f"{variant}_strategy_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
        if results:
            import json
            import dataclasses
            dl_right.download_button(
                "⬇ JSON Results",
                data=json.dumps([dataclasses.asdict(r) for r in results], indent=2),
                file_name=f"{variant}_results.json",
                mime="application/json",
                use_container_width=True,
            )

    st.divider()
    if st.button("← Rebuild", use_container_width=False):
        st.session_state["view"] = "build"
        st.rerun()


# ---------------------------------------------------------------------------
# Play panel
# ---------------------------------------------------------------------------

def _render_play_panel() -> None:
    lb = st.session_state.get("leaderboard") or []
    best_name = _agent_short_name(lb[0].agent_name) if lb else "Engine"

    st.markdown(f"### You vs {best_name}")

    fen = st.session_state.get("play_fen", chess.STARTING_FEN)
    play_moves: list[str] = st.session_state.get("play_moves", [])
    play_status: str = st.session_state.get("play_status", "ongoing")

    # Build SAN move list from UCI history
    board_replay = chess.Board()
    san_moves: list[str] = []
    for uci in play_moves:
        try:
            move = chess.Move.from_uci(uci)
            san_moves.append(board_replay.san(move))
            board_replay.push(move)
        except Exception:
            break

    # Render move list as paired rows
    pairs: list[str] = []
    for i in range(0, len(san_moves), 2):
        white_san = san_moves[i]
        black_san = san_moves[i + 1] if i + 1 < len(san_moves) else ""
        pairs.append(f"{i // 2 + 1}. {white_san}  {black_san}")
    move_html = "<br>".join(pairs) if pairs else "<span style='color:#888'>No moves yet</span>"
    st.markdown(
        f'<div class="move-list-scroll">{move_html}</div>',
        unsafe_allow_html=True,
    )

    # Status
    board_now = chess.Board(fen)
    if play_status == "checkmate":
        status_text = "Checkmate!"
    elif play_status in ("stalemate", "draw"):
        status_text = "Game drawn."
    elif board_now.turn == chess.WHITE:
        status_text = "Your turn (White)"
        if board_now.is_check():
            status_text += " — Check!"
    else:
        status_text = "Engine thinking…"

    st.markdown(
        f'<div style="color:#629924;font-weight:600;margin:8px 0;">{status_text}</div>',
        unsafe_allow_html=True,
    )

    # Move input
    if play_status == "ongoing" and board_now.turn == chess.WHITE:
        move_input = st.text_input(
            "Your move (e.g. e4, Nf3, O-O)",
            key="play_move_input",
            label_visibility="visible",
        )
        if st.button("Make Move", use_container_width=True):
            if move_input.strip():
                try:
                    board_tmp = chess.Board(fen)
                    move = board_tmp.parse_san(move_input.strip())
                    if move in board_tmp.legal_moves:
                        board_tmp.push(move)
                        play_moves = play_moves + [move.uci()]
                        new_fen = board_tmp.fen()
                        # Check game over after player move
                        if board_tmp.is_checkmate():
                            st.session_state.update(
                                play_fen=new_fen,
                                play_moves=play_moves,
                                play_status="checkmate",
                            )
                        elif board_tmp.is_stalemate() or board_tmp.is_insufficient_material():
                            st.session_state.update(
                                play_fen=new_fen,
                                play_moves=play_moves,
                                play_status="stalemate",
                            )
                        else:
                            # Engine reply
                            reply_uci = _engine_reply(new_fen)
                            if reply_uci:
                                board_reply = chess.Board(new_fen)
                                board_reply.push(chess.Move.from_uci(reply_uci))
                                play_moves = play_moves + [reply_uci]
                                reply_fen = board_reply.fen()
                                if board_reply.is_checkmate():
                                    status = "checkmate"
                                elif board_reply.is_stalemate() or board_reply.is_insufficient_material():
                                    status = "stalemate"
                                else:
                                    status = "ongoing"
                                st.session_state.update(
                                    play_fen=reply_fen,
                                    play_moves=play_moves,
                                    play_status=status,
                                )
                            else:
                                st.session_state.update(
                                    play_fen=new_fen,
                                    play_moves=play_moves,
                                )
                        st.rerun()
                    else:
                        st.error("Illegal move.")
                except Exception as exc:
                    st.error(f"Invalid move: {exc}")

    st.divider()

    # Controls row
    ctrl1, ctrl2, ctrl3 = st.columns(3)
    if ctrl1.button("New Game", use_container_width=True):
        st.session_state.update(
            play_fen=chess.STARTING_FEN,
            play_moves=[],
            play_status="ongoing",
        )
        st.rerun()

    flip_label = "Flip Board ✓" if st.session_state.get("play_flipped") else "Flip Board"
    if ctrl2.button(flip_label, use_container_width=True):
        st.session_state["play_flipped"] = not st.session_state.get("play_flipped", False)
        st.rerun()

    if ctrl3.button("← Back to Analysis", use_container_width=True):
        st.session_state["view"] = "analysis"
        st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _init_session_state()

    # Apply global CSS
    st.markdown(_CSS, unsafe_allow_html=True)

    # Handle error state
    if st.session_state.get("error"):
        st.error(st.session_state["error"])
        if st.button("Clear error and reset"):
            st.session_state["error"] = None
            st.session_state["running"] = False
            st.session_state["view"] = "build"
            st.rerun()
        return

    # Auto-transition: if running flag dropped but view is still "live", push to analysis
    if not st.session_state.get("running") and st.session_state.get("view") == "live":
        if st.session_state.get("leaderboard") is not None:
            st.session_state["view"] = "analysis"

    st.markdown(HEADER_HTML, unsafe_allow_html=True)
    board_col, panel_col = st.columns([11, 8])

    with board_col:
        _render_board_area()

    with panel_col:
        view = st.session_state.get("view", "build")
        if view == "live":
            _render_live_panel()
        elif view == "analysis":
            _render_analysis_panel()
        elif view == "play":
            _render_play_panel()
        else:
            _render_build_panel()


if __name__ == "__main__":
    main()
