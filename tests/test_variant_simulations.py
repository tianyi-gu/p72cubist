"""End-to-end stress tests for the four newer variants.

Verifies starting position, move generation, and self-play termination for
King of the Hill, Three-Check, Chess960, and Horde. Mirrors the coverage
that test_atomic / test_antichess provide for the older variants.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.board import Board
from variants.base import get_apply_move, get_generate_legal_moves
from variants.chess960 import chess960_starting_position
from variants.horde import horde_starting_position
from variants.king_of_the_hill import apply_koth_move
from variants.three_check import apply_three_check_move
from simulation.random_agent import RandomAgent
from simulation.game import play_game


_NEW_VARIANTS = ["kingofthehill", "threecheck", "chess960", "horde"]


# ---------------------------------------------------------------------------
# Starting-position structural tests
# ---------------------------------------------------------------------------

class TestKothStartingPosition:
    def test_starts_from_standard_position(self):
        b = Board.starting_position()
        # KOTH uses the standard chess starting position
        assert b.find_king("w") == (0, 4)
        assert b.find_king("b") == (7, 4)
        assert b.side_to_move == "w"

    def test_initial_legal_moves_is_20(self):
        b = Board.starting_position()
        legal = get_generate_legal_moves("kingofthehill")(b)
        assert len(legal) == 20


class TestThreeCheckStartingPosition:
    def test_starts_from_standard_position(self):
        b = Board.starting_position()
        assert b.find_king("w") == (0, 4)
        assert b.check_count == {"w": 0, "b": 0}

    def test_initial_legal_moves_is_20(self):
        b = Board.starting_position()
        legal = get_generate_legal_moves("threecheck")(b)
        assert len(legal) == 20


class TestChess960StartingPosition:
    def test_back_rank_is_shuffled_but_valid(self):
        b = chess960_starting_position(seed=1)
        # White back rank (row 0) — must contain exactly K, Q, 2R, 2N, 2B
        back = b.grid[0]
        from collections import Counter
        c = Counter(back)
        assert c == Counter({"R": 2, "N": 2, "B": 2, "Q": 1, "K": 1})

    def test_king_between_two_rooks(self):
        for seed in range(20):
            b = chess960_starting_position(seed=seed)
            back = b.grid[0]
            r1 = back.index("R")
            k = back.index("K")
            r2 = back.index("R", r1 + 1)
            assert r1 < k < r2, f"seed {seed}: rooks={r1},{r2} king={k}"

    def test_bishops_on_opposite_colors(self):
        for seed in range(20):
            b = chess960_starting_position(seed=seed)
            back = b.grid[0]
            bishops = [i for i, p in enumerate(back) if p == "B"]
            assert len(bishops) == 2
            # Opposite colors = different parity of column index
            assert (bishops[0] % 2) != (bishops[1] % 2), f"seed {seed}: bishops={bishops}"

    def test_black_back_rank_mirrors_white(self):
        for seed in [0, 5, 42, 123]:
            b = chess960_starting_position(seed=seed)
            white = b.grid[0]
            black = b.grid[7]
            assert [p.lower() if p else None for p in white] == black

    def test_pawns_on_rank_2_and_7(self):
        b = chess960_starting_position(seed=0)
        assert b.grid[1] == ["P"] * 8
        assert b.grid[6] == ["p"] * 8

    def test_castling_disabled(self):
        b = chess960_starting_position(seed=0)
        assert b.castling_rights == {"K": False, "Q": False, "k": False, "q": False}


class TestHordeStartingPosition:
    def test_white_has_36_pawns_and_no_other_pieces(self):
        b = horde_starting_position()
        white_pieces = []
        for row in range(8):
            for col in range(8):
                p = b.grid[row][col]
                if p is not None and p.isupper():
                    white_pieces.append(p)
        assert len(white_pieces) == 36, f"got {len(white_pieces)} white pieces"
        assert all(p == "P" for p in white_pieces), f"non-pawn whites: {set(white_pieces)}"

    def test_white_has_no_king(self):
        b = horde_starting_position()
        # find_king returns None if no king of that color
        assert b.find_king("w") is None

    def test_black_has_standard_back_rank_and_pawns(self):
        b = horde_starting_position()
        assert b.grid[7] == ["r", "n", "b", "q", "k", "b", "n", "r"]
        assert b.grid[6] == ["p"] * 8
        assert b.find_king("b") == (7, 4)

    def test_white_pawn_positions(self):
        b = horde_starting_position()
        # Rows 0-3: all white pawns
        for r in range(4):
            assert b.grid[r] == ["P"] * 8, f"row {r} not all pawns: {b.grid[r]}"
        # Row 4: pawns on b5, c5, f5, g5 only
        expected_row4 = [None] * 8
        expected_row4[1] = "P"
        expected_row4[2] = "P"
        expected_row4[5] = "P"
        expected_row4[6] = "P"
        assert b.grid[4] == expected_row4

    def test_initial_legal_moves_for_white(self):
        b = horde_starting_position()
        legal = get_generate_legal_moves("horde")(b)
        # White has plenty of pawn moves available
        assert len(legal) > 0


# ---------------------------------------------------------------------------
# End-to-end self-play simulations: each variant should terminate with a
# well-formed GameResult under tight time budgets.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant", _NEW_VARIANTS)
def test_random_self_play_terminates(variant):
    white = RandomAgent(seed=1)
    black = RandomAgent(seed=2)
    result = play_game(white, black, variant=variant, depth=1, max_moves=40, seed=42)
    assert result.moves >= 1
    assert result.moves <= 40
    assert result.termination_reason in (
        "checkmate", "stalemate", "move_cap", "variant_win", "king_exploded",
    )
    # winner is "w", "b", or None — all valid
    assert result.winner in ("w", "b", None)
    # Move list should match move count
    assert len(result.move_list) == result.moves


# ---------------------------------------------------------------------------
# Variant-specific win-condition tests
# ---------------------------------------------------------------------------

class TestKothWinCondition:
    def test_king_to_center_wins(self):
        # Position: white king on d3 about to move to d4 (a center square)
        from core.move import Move
        b = Board()
        b.grid[2][3] = "K"  # white king on d3 = (row 2, col 3)
        b.grid[7][4] = "k"  # black king on e8
        b.side_to_move = "w"
        b.castling_rights = {"K": False, "Q": False, "k": False, "q": False}
        # Move king to d4 = (3, 3) — center
        move = Move(start=(2, 3), end=(3, 3))
        new_board = apply_koth_move(b, move)
        assert new_board.winner == "w"

    def test_king_off_center_does_not_win(self):
        from core.move import Move
        b = Board()
        b.grid[0][4] = "K"
        b.grid[7][4] = "k"
        b.side_to_move = "w"
        b.castling_rights = {"K": False, "Q": False, "k": False, "q": False}
        move = Move(start=(0, 4), end=(1, 4))  # move to e2 — not center
        new_board = apply_koth_move(b, move)
        assert new_board.winner is None


class TestThreeCheckWinCondition:
    def test_first_check_increments_counter(self):
        from core.move import Move
        b = Board()
        b.grid[0][4] = "K"
        b.grid[7][4] = "k"
        b.grid[6][4] = "Q"  # white queen on e7 — gives check by moving to e8? no.
        # Position queen so a move actually delivers check.
        # Setup: white queen on e1, black king on e8, queen moves to e7 → check.
        b = Board()
        b.grid[0][3] = "K"  # white king d1 (out of way)
        b.grid[7][4] = "k"  # black king e8
        b.grid[0][4] = "Q"  # white queen e1
        b.side_to_move = "w"
        b.castling_rights = {"K": False, "Q": False, "k": False, "q": False}
        move = Move(start=(0, 4), end=(6, 4))  # Q e1 -> e7, attacks k on e8
        new_board = apply_three_check_move(b, move)
        assert new_board.check_count["w"] == 1
        assert new_board.winner is None  # only first check

    def test_third_check_wins(self):
        from core.move import Move
        b = Board()
        b.grid[0][3] = "K"
        b.grid[7][4] = "k"
        b.grid[0][4] = "Q"
        b.side_to_move = "w"
        b.castling_rights = {"K": False, "Q": False, "k": False, "q": False}
        b.check_count = {"w": 2, "b": 0}  # already 2 checks
        move = Move(start=(0, 4), end=(6, 4))  # delivers check #3
        new_board = apply_three_check_move(b, move)
        assert new_board.check_count["w"] == 3
        assert new_board.winner == "w"


class TestHordeWinCondition:
    def test_black_wins_when_white_has_no_pieces(self):
        from variants.horde import apply_horde_move
        from core.move import Move
        # Setup: only one white pawn on a1, black takes it next move.
        b = Board()
        b.grid[0][0] = "P"   # white pawn a1
        b.grid[7][4] = "k"
        b.grid[1][1] = "n"   # black knight on b2 about to take pawn
        b.side_to_move = "b"
        b.castling_rights = {"K": False, "Q": False, "k": False, "q": False}
        # Move knight to a1 capturing the pawn? Knight at b2=(1,1) cannot reach a1=(0,0)
        # — knights move L-shape. Let's place black queen instead.
        b = Board()
        b.grid[0][0] = "P"
        b.grid[7][4] = "k"
        b.grid[1][1] = "q"   # black queen on b2
        b.side_to_move = "b"
        b.castling_rights = {"K": False, "Q": False, "k": False, "q": False}
        # Queen captures pawn on a1
        move = Move(start=(1, 1), end=(0, 0))
        new_board = apply_horde_move(b, move)
        assert new_board.winner == "b"

    def test_white_still_alive_means_no_winner(self):
        from variants.horde import apply_horde_move
        from core.move import Move
        b = horde_starting_position()
        # A simple white pawn move shouldn't trigger a win
        move = Move(start=(3, 4), end=(4, 4))  # e4 advance
        new_board = apply_horde_move(b, move)
        assert new_board.winner is None
