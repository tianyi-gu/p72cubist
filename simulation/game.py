"""Game simulation for EngineLab.

Plays a game between two agents using the specified variant rules.
"""

from dataclasses import dataclass

from core.board import Board
from core.move_generation import generate_legal_moves, is_in_check
from agents.feature_subset_agent import FeatureSubsetAgent
from search.alpha_beta import AlphaBetaEngine
from variants.base import get_apply_move, get_generate_legal_moves


@dataclass
class GameResult:
    """Result of a completed game."""

    white_agent: str
    black_agent: str
    winner: str | None        # "w", "b", or None (draw)
    moves: int                # total plies
    termination_reason: str   # "checkmate" | "stalemate" | "move_cap"
    white_avg_nodes: float
    black_avg_nodes: float
    white_avg_time: float
    black_avg_time: float


def play_game(
    white_agent: FeatureSubsetAgent,
    black_agent: FeatureSubsetAgent,
    variant: str = "standard",
    depth: int = 1,
    max_moves: int = 80,
    seed: int | None = None,
) -> GameResult:
    """Play a complete game between two agents.

    Returns a GameResult with outcome and statistics.
    """
    board = Board.starting_position()
    apply_fn = get_apply_move(variant)
    gen_legal_fn = get_generate_legal_moves(variant)

    white_engine = AlphaBetaEngine(white_agent, depth)
    black_engine = AlphaBetaEngine(black_agent, depth)

    white_nodes: list[int] = []
    black_nodes: list[int] = []
    white_times: list[float] = []
    black_times: list[float] = []

    for ply in range(max_moves):
        legal = gen_legal_fn(board)

        if not legal:
            # No legal moves — checkmate or stalemate
            color = board.side_to_move
            if is_in_check(board, color):
                # Checkmate: the side to move loses
                winner = "b" if color == "w" else "w"
                return GameResult(
                    white_agent=white_agent.name,
                    black_agent=black_agent.name,
                    winner=winner,
                    moves=ply,
                    termination_reason="checkmate",
                    white_avg_nodes=_avg(white_nodes),
                    black_avg_nodes=_avg(black_nodes),
                    white_avg_time=_avg(white_times),
                    black_avg_time=_avg(black_times),
                )
            else:
                # Stalemate
                return GameResult(
                    white_agent=white_agent.name,
                    black_agent=black_agent.name,
                    winner=None,
                    moves=ply,
                    termination_reason="stalemate",
                    white_avg_nodes=_avg(white_nodes),
                    black_avg_nodes=_avg(black_nodes),
                    white_avg_time=_avg(white_times),
                    black_avg_time=_avg(black_times),
                )

        if board.side_to_move == "w":
            move = white_engine.choose_move(board)
            white_nodes.append(white_engine.nodes_searched)
            white_times.append(white_engine.search_time_seconds)
        else:
            move = black_engine.choose_move(board)
            black_nodes.append(black_engine.nodes_searched)
            black_times.append(black_engine.search_time_seconds)

        board = apply_fn(board, move)

    # Move cap reached — draw
    return GameResult(
        white_agent=white_agent.name,
        black_agent=black_agent.name,
        winner=None,
        moves=max_moves,
        termination_reason="move_cap",
        white_avg_nodes=_avg(white_nodes),
        black_avg_nodes=_avg(black_nodes),
        white_avg_time=_avg(white_times),
        black_avg_time=_avg(black_times),
    )


def _avg(values: list[int | float]) -> float:
    """Average of a list, 0.0 if empty."""
    if not values:
        return 0.0
    return sum(values) / len(values)
