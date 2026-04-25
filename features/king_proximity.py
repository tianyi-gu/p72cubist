"""King proximity evaluation feature for atomic chess."""

from core.board import Board
from core.types import piece_color


def king_proximity(board: Board, color: str) -> float:
    """Count of own non-pawns adjacent to enemy king minus enemy non-pawns adjacent to own king.

    Adjacent = Chebyshev distance 1 (the 8 squares surrounding the king).
    A piece adjacent to the king can immediately capture into the king's square or
    onto a neighboring square, triggering an explosion that kills the king.
    Pawns excluded: they survive explosions in atomic chess.

    Positive = your pieces are next to their king; negative = their pieces are next to yours.
    """
    opp = "b" if color == "w" else "w"

    own_king_sq = board.find_king(color)
    enemy_king_sq = board.find_king(opp)

    def _adjacent_count(king_sq, attacker_color: str) -> float:
        if king_sq is None:
            return 0.0
        kr, kc = king_sq
        count = 0.0
        for row in range(8):
            for col in range(8):
                piece = board.get_piece((row, col))
                if piece is None or piece_color(piece) != attacker_color or piece.upper() == "P":
                    continue
                if max(abs(row - kr), abs(col - kc)) == 1:
                    count += 1.0
        return count

    offensive = _adjacent_count(enemy_king_sq, color)
    defensive = _adjacent_count(own_king_sq, opp)
    return offensive - defensive
