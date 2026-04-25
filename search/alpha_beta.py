"""Alpha-beta negamax search engine for EngineLab.

Foundation provides basic depth-1 search with move ordering
(captures first).
"""

import time

from core.board import Board
from core.move import Move
from core.move_generation import generate_legal_moves
from core.apply_move import apply_move
from agents.feature_subset_agent import FeatureSubsetAgent
from agents.evaluation import evaluate, WIN_SCORE, LOSS_SCORE


class AlphaBetaEngine:
    """Alpha-beta search engine using negamax formulation."""

    def __init__(self, agent: FeatureSubsetAgent, depth: int) -> None:
        self.agent = agent
        self.depth = depth
        self._nodes_searched = 0
        self._search_time = 0.0

    @property
    def nodes_searched(self) -> int:
        return self._nodes_searched

    @property
    def search_time_seconds(self) -> float:
        return self._search_time

    def choose_move(self, board: Board) -> Move:
        """Select the best move by alpha-beta search."""
        start_time = time.monotonic()
        self._nodes_searched = 0

        legal = generate_legal_moves(board)
        if not legal:
            raise ValueError("No legal moves available")

        # Order moves: captures first for better pruning
        legal = self._order_moves(board, legal)

        best_move = legal[0]
        best_score = LOSS_SCORE - 1
        color = board.side_to_move

        for move in legal:
            new_board = apply_move(board, move)
            score = -self._negamax(new_board, self.depth - 1,
                                   LOSS_SCORE, WIN_SCORE,
                                   "b" if color == "w" else "w")
            if score > best_score:
                best_score = score
                best_move = move

        self._search_time = time.monotonic() - start_time
        return best_move

    def _negamax(self, board: Board, depth: int,
                 alpha: int, beta: int, color: str) -> float:
        """Negamax with alpha-beta pruning."""
        self._nodes_searched += 1

        if board.is_terminal():
            return evaluate(board, color, self.agent)

        if depth == 0:
            return evaluate(board, color, self.agent)

        legal = generate_legal_moves(board)
        if not legal:
            # No legal moves: checkmate or stalemate
            from core.move_generation import is_in_check
            if is_in_check(board, color):
                return LOSS_SCORE
            return 0.0  # stalemate

        legal = self._order_moves(board, legal)

        best = LOSS_SCORE
        for move in legal:
            new_board = apply_move(board, move)
            score = -self._negamax(new_board, depth - 1, -beta, -alpha,
                                   "b" if color == "w" else "w")
            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break

        return best

    @staticmethod
    def _order_moves(board: Board, moves: list[Move]) -> list[Move]:
        """Order moves with captures first for better pruning."""
        captures = []
        non_captures = []
        for move in moves:
            if board.get_piece(move.end) is not None:
                captures.append(move)
            else:
                non_captures.append(move)
        return captures + non_captures
