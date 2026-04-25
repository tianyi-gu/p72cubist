"""Evaluation functions for EngineLab.

Foundation provides material-only evaluation. Full feature evaluation
is implemented in Area 1.
"""

from core.board import Board
from core.types import piece_color
from agents.feature_subset_agent import FeatureSubsetAgent

WIN_SCORE: int = 10_000
LOSS_SCORE: int = -10_000

# Standard piece values
_PIECE_VALUES = {
    "P": 1, "N": 3, "B": 3, "R": 5, "Q": 9,
    "p": 1, "n": 3, "b": 3, "r": 5, "q": 9,
}


def normalize_feature_value(x: float) -> float:
    """Clip to [-10, 10] and normalize to [-1, 1]."""
    return max(-10.0, min(10.0, x)) / 10.0


def _material(board: Board, color: str) -> float:
    """Raw material difference: own material minus opponent material."""
    own = 0
    opp = 0
    for row in range(8):
        for col in range(8):
            piece = board.get_piece((row, col))
            if piece is None or piece.upper() == "K":
                continue
            value = _PIECE_VALUES.get(piece, 0)
            if piece_color(piece) == color:
                own += value
            else:
                opp += value
    return float(own - opp)


# Foundation feature registry — only material is implemented
_FOUNDATION_FEATURES = {
    "material": _material,
}


def evaluate(board: Board, color: str, agent: FeatureSubsetAgent) -> float:
    """Weighted sum of normalized features. WIN/LOSS for terminals."""
    if board.winner is not None:
        if board.winner == color:
            return WIN_SCORE
        elif board.winner == "draw":
            return 0.0
        else:
            return LOSS_SCORE

    total = 0.0
    for feat_name in agent.features:
        feat_fn = _FOUNDATION_FEATURES.get(feat_name)
        if feat_fn is not None:
            raw = feat_fn(board, color)
            total += agent.weights[feat_name] * normalize_feature_value(raw)
    return total


def contributions(
    board: Board, color: str, agent: FeatureSubsetAgent,
) -> dict[str, float]:
    """Per-feature weighted contribution."""
    result = {}
    for feat_name in agent.features:
        feat_fn = _FOUNDATION_FEATURES.get(feat_name)
        if feat_fn is not None:
            raw = feat_fn(board, color)
            result[feat_name] = agent.weights[feat_name] * normalize_feature_value(raw)
        else:
            result[feat_name] = 0.0
    return result
